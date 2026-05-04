import asyncio
import logging
import random
from datetime import datetime, timedelta

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fakecorpo_shared.schemas.clock import ClockTick
from fakecorpo_shared.schemas.procurement import PurchaseOrderArrived

from .config import Settings
from .events import EventPublisher
from .models import SimCheckpoint
from .production import (
    advance_in_progress_batches,
    apply_arrival,
    maybe_start_batches,
)

log = logging.getLogger(__name__)

CHECKPOINT_ROASTING = "roasting_decision"


async def _get_checkpoint(session: AsyncSession, name: str) -> SimCheckpoint | None:
    return (
        await session.scalars(
            select(SimCheckpoint).where(SimCheckpoint.name == name)
        )
    ).one_or_none()


async def _upsert_checkpoint(session: AsyncSession, name: str, sim_time: datetime) -> None:
    cp = await _get_checkpoint(session, name)
    if cp is None:
        session.add(SimCheckpoint(name=name, last_sim_time=sim_time))
    else:
        cp.last_sim_time = sim_time


class TopicConsumer:
    """Single Kafka consumer subscribed to two topics:
       - `clock.tick`              (ticker → advance batches + maybe start new ones)
       - `procurement.po_arrived`  (procurement → credit green inventory)
    Dispatch happens on `msg.topic`.
    """

    def __init__(
        self,
        settings: Settings,
        consumer: AIOKafkaConsumer,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: EventPublisher,
    ) -> None:
        self.settings = settings
        self.consumer = consumer
        self.session_factory = session_factory
        self.publisher = publisher
        self.rng_roasting = random.Random(settings.random_seed)
        self.rng_telemetry = random.Random(settings.random_seed + 1)
        self.rng_completion = random.Random(settings.random_seed + 2)
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="production-consumer")
        log.info(
            "consumer.started topics=%s group=%s roasting_every=%dd",
            (self.settings.kafka_topic_tick, self.settings.kafka_topic_po_arrived),
            self.settings.kafka_consumer_group,
            self.settings.roasting_decision_interval_sim_days,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        log.info("consumer.stopped")

    async def _run(self) -> None:
        try:
            async for msg in self.consumer:
                if self._stop.is_set():
                    break
                try:
                    if msg.topic == self.settings.kafka_topic_tick:
                        tick = ClockTick.model_validate_json(msg.value)
                        await self._handle_tick(tick)
                    elif msg.topic == self.settings.kafka_topic_po_arrived:
                        arrival = PurchaseOrderArrived.model_validate_json(msg.value)
                        await self._handle_arrival(arrival)
                    else:
                        log.warning("consumer.unknown_topic topic=%s", msg.topic)
                except Exception:
                    log.exception(
                        "consumer.handler_error topic=%s offset=%d",
                        msg.topic, msg.offset,
                    )
        except asyncio.CancelledError:
            pass

    async def _handle_tick(self, tick: ClockTick) -> None:
        if tick.paused:
            return

        async with self.session_factory() as session:
            await advance_in_progress_batches(
                session=session,
                publisher=self.publisher,
                settings=self.settings,
                rng=self.rng_telemetry,
                sim_now=tick.sim_time,
            )
            await self._maybe_start_batches(session, tick.sim_time)
            await session.commit()

    async def _maybe_start_batches(self, session: AsyncSession, sim_time: datetime) -> None:
        cp = await _get_checkpoint(session, CHECKPOINT_ROASTING)
        if cp is None:
            await _upsert_checkpoint(session, CHECKPOINT_ROASTING, sim_time)
            log.info("consumer.roasting_checkpoint_initialized at=%s", sim_time.isoformat())
            return
        if sim_time - cp.last_sim_time < timedelta(days=self.settings.roasting_decision_interval_sim_days):
            return
        await maybe_start_batches(
            session=session,
            publisher=self.publisher,
            settings=self.settings,
            rng=self.rng_roasting,
            sim_now=sim_time,
        )
        await _upsert_checkpoint(session, CHECKPOINT_ROASTING, sim_time)

    async def _handle_arrival(self, arrival: PurchaseOrderArrived) -> None:
        async with self.session_factory() as session:
            await apply_arrival(session, arrival, sim_now=arrival.sim_actual_arrival or arrival.sim_expected_arrival)
            await session.commit()
