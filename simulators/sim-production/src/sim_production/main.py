import asyncio
import logging
import signal
import sys

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import Settings
from .consumer import TopicConsumer
from .db import (
    create_all_tables,
    ensure_database_exists,
    make_engine,
    make_session_factory,
)
from .events import EventPublisher
from .seed import seed_master_data


async def amain() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    log = logging.getLogger("sim_production")
    log.info(
        "startup settings=%s",
        settings.model_dump(exclude={"database_url", "database_bootstrap_url"}),
    )

    await ensure_database_exists(settings.database_bootstrap_url, settings.database_name)

    engine = make_engine(settings.database_url)
    await create_all_tables(engine)
    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        await seed_master_data(session)

    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
    await producer.start()
    publisher = EventPublisher(
        producer,
        settings.kafka_topic_batch_started,
        settings.kafka_topic_batch_completed,
        settings.kafka_topic_telemetry,
    )

    consumer = AIOKafkaConsumer(
        settings.kafka_topic_tick,
        settings.kafka_topic_po_arrived,
        bootstrap_servers=settings.kafka_brokers,
        group_id=settings.kafka_consumer_group,
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await consumer.start()

    topic_consumer = TopicConsumer(settings, consumer, session_factory, publisher)
    await topic_consumer.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop_event.set())
    log.info("startup.ready")
    try:
        await stop_event.wait()
    finally:
        log.info("shutdown.begin")
        await topic_consumer.stop()
        await consumer.stop()
        await producer.stop()
        await engine.dispose()
        log.info("shutdown.complete")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
