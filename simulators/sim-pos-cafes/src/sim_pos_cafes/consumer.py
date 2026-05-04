import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fakecorpo_shared.schemas.clock import ClockTick

from .config import Settings
from .events import EventPublisher
from .models import SimCheckpoint
from .pos import process_sim_hour

log = logging.getLogger(__name__)

CHECKPOINT_HOUR = "pos_last_processed_hour"


def _floor_to_hour(t: datetime) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


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
    """Consumes `clock.tick`. The POS processor walks one sim-hour at a time —
    if the clock advances faster than real time (high speed_ratio), we
    catch up by iterating, capped at `max_hours_per_tick` to keep
    individual transactions snappy."""

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
        self.rng_demand = random.Random(settings.random_seed)
        self.rng_weather = random.Random(settings.random_seed + 1)
        self.rng_picks = random.Random(settings.random_seed + 2)
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="pos-tick-consumer")
        log.info(
            "consumer.started topic=%s group=%s max_catchup_hours_per_tick=%d",
            self.settings.kafka_topic_tick,
            self.settings.kafka_consumer_group,
            self.settings.max_hours_per_tick,
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
                    await self._handle_tick(tick)
                except Exception:
                    log.exception("consumer.handler_error offset=%d", msg.offset)
        except asyncio.CancelledError:
            pass

    async def _handle_tick(self, tick: ClockTick) -> None:
        if tick.paused:
            return
        current_hour = _floor_to_hour(tick.sim_time)

        async with self.session_factory() as session:
            cp = await _get_checkpoint(session, CHECKPOINT_HOUR)
            if cp is None:
                # Initialize anchor at the current hour, do not run yet
                # (avoid generating a backlog burst on first ever tick).
                await _upsert_checkpoint(session, CHECKPOINT_HOUR, current_hour)
                await session.commit()
                log.info("consumer.checkpoint_initialized at=%s", current_hour.isoformat())
                return

            last_hour = _floor_to_hour(cp.last_sim_time)
            if current_hour <= last_hour:
                return

            # Iterate hour by hour; cap to avoid pathological catch-up bursts.
            target = current_hour
            cap = last_hour + timedelta(hours=self.settings.max_hours_per_tick)
            if target > cap:
                target = cap

            h = last_hour + timedelta(hours=1)
            while h <= target:
                await process_sim_hour(
                    session=session,
                    publisher=self.publisher,
                    settings=self.settings,
                    rng_demand=self.rng_demand,
                    rng_weather=self.rng_weather,
                    rng_picks=self.rng_picks,
                    sim_hour=h,
                )
                h += timedelta(hours=1)

            await _upsert_checkpoint(session, CHECKPOINT_HOUR, target)
            await session.commit()
