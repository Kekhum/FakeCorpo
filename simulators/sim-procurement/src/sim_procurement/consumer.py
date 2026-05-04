import asyncio
import logging
import random
from datetime import datetime, timedelta

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fakecorpo_shared.schemas.clock import ClockTick

from .arrivals import run_arrivals_scan
from .config import Settings
from .events import EventPublisher
from .models import SimCheckpoint
from .procurement import run_procurement_round

log = logging.getLogger(__name__)

CHECKPOINT_PROCUREMENT = "procurement_round"
CHECKPOINT_ARRIVALS = "arrivals_scan"


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


class TickConsumer:
    """Consumes `clock.tick`. On each tick:

       1. If a sim-week elapsed since last procurement round → place new POs.
       2. If a sim-day  elapsed since last arrivals scan    → settle in-transit POs.

    Both branches are independent and idempotent via DB checkpoints.
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
        # Two distinct RNGs so that touching one doesn't desync the other.
        self.rng_procurement = random.Random(settings.random_seed)
        self.rng_arrivals = random.Random(settings.random_seed + 1)
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="procurement-tick-consumer")
        log.info(
            "consumer.started topic=%s group=%s procurement_every=%dd arrivals_every=%dd",
            self.settings.kafka_topic_tick,
            self.settings.kafka_consumer_group,
            self.settings.run_interval_sim_days,
            self.settings.arrivals_interval_sim_days,
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
                    tick = ClockTick.model_validate_json(msg.value)
                except Exception:
                    log.exception("consumer.bad_message offset=%d", msg.offset)
                    continue
                await self._handle_tick(tick)
        except asyncio.CancelledError:
            pass

    async def _handle_tick(self, tick: ClockTick) -> None:
        if tick.paused:
            return

        async with self.session_factory() as session:
            await self._maybe_run_procurement(session, tick.sim_time)
            await self._maybe_run_arrivals(session, tick.sim_time)
            await session.commit()

    async def _maybe_run_procurement(self, session: AsyncSession, sim_time: datetime) -> None:
        cp = await _get_checkpoint(session, CHECKPOINT_PROCUREMENT)
        if cp is None:
            await _upsert_checkpoint(session, CHECKPOINT_PROCUREMENT, sim_time)
            log.info("consumer.procurement_checkpoint_initialized at=%s", sim_time.isoformat())
            return
        if sim_time - cp.last_sim_time < timedelta(days=self.settings.run_interval_sim_days):
            return
        await run_procurement_round(
            session=session,
            publisher=self.publisher,
            settings=self.settings,
            rng=self.rng_procurement,
            sim_now=sim_time,
        )
        await _upsert_checkpoint(session, CHECKPOINT_PROCUREMENT, sim_time)

    async def _maybe_run_arrivals(self, session: AsyncSession, sim_time: datetime) -> None:
        cp = await _get_checkpoint(session, CHECKPOINT_ARRIVALS)
        if cp is None:
            await _upsert_checkpoint(session, CHECKPOINT_ARRIVALS, sim_time)
            log.info("consumer.arrivals_checkpoint_initialized at=%s", sim_time.isoformat())
            return
        if sim_time - cp.last_sim_time < timedelta(days=self.settings.arrivals_interval_sim_days):
            return
        await run_arrivals_scan(
            session=session,
            publisher=self.publisher,
            settings=self.settings,
            rng=self.rng_arrivals,
            sim_now=sim_time,
        )
        await _upsert_checkpoint(session, CHECKPOINT_ARRIVALS, sim_time)
