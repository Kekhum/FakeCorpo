import asyncio
import logging
import signal
import sys

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import Settings
from .consumer import TickConsumer
from .db import (
    apply_post_create_migrations,
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
    log = logging.getLogger("sim_procurement")
    log.info("startup settings=%s", settings.model_dump(exclude={"database_url", "database_bootstrap_url"}))

    # 1) ensure DB exists
    await ensure_database_exists(
        settings.database_bootstrap_url, settings.database_name
    )

    # 2) connect to our DB, create tables, apply incremental migrations, seed master data
    engine = make_engine(settings.database_url)
    await create_all_tables(engine)
    await apply_post_create_migrations(engine)
    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        await seed_master_data(session)

    # 3) Kafka producer for procurement.po_created and procurement.po_arrived
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
    await producer.start()
    publisher = EventPublisher(
        producer,
        settings.kafka_topic_po_created,
        settings.kafka_topic_po_arrived,
    )

    # 4) Kafka consumer for clock.tick
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_tick,
        bootstrap_servers=settings.kafka_brokers,
        group_id=settings.kafka_consumer_group,
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await consumer.start()

    tick_consumer = TickConsumer(settings, consumer, session_factory, publisher)
    await tick_consumer.start()

    # 5) wait for SIGTERM/SIGINT
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in _platform_signals():
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows: add_signal_handler not implemented for asyncio
            signal.signal(sig, lambda *_: stop_event.set())
    log.info("startup.ready")
    try:
        await stop_event.wait()
    finally:
        log.info("shutdown.begin")
        await tick_consumer.stop()
        await consumer.stop()
        await producer.stop()
        await engine.dispose()
        log.info("shutdown.complete")


def _platform_signals() -> list[int]:
    sigs: list[int] = [signal.SIGINT, signal.SIGTERM]
    return sigs


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
