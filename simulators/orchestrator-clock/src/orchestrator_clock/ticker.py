import asyncio
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from redis.asyncio import Redis

from fakecorpo_shared.schemas.clock import ClockState, ClockTick, advance

from .config import Settings
from .state import load_state, next_tick_id, save_state

log = logging.getLogger(__name__)


class Ticker:
    """Background loop: every `tick_interval_seconds` advance state and publish a tick."""

    def __init__(
        self,
        settings: Settings,
        redis: Redis,
        producer: AIOKafkaProducer,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.producer = producer
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="clock-ticker")
        log.info("ticker.started interval=%.2fs", self.settings.tick_interval_seconds)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        log.info("ticker.stopped")

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception:
                log.exception("ticker.error")
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self.settings.tick_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _tick_once(self) -> None:
        state = await load_state(self.redis)
        if state is None:
            log.warning("ticker.no_state")
            return

        new_state = advance(state, self.settings.tick_interval_seconds)
        await save_state(self.redis, new_state)

        tick_id = await next_tick_id(self.redis)
        tick = ClockTick(
            tick_id=tick_id,
            sim_time=new_state.sim_time,
            real_time=datetime.now(timezone.utc),
            speed_ratio=new_state.speed_ratio,
            paused=new_state.paused,
        )
        await self.producer.send_and_wait(
            self.settings.kafka_topic_tick,
            value=tick.model_dump_json().encode("utf-8"),
            key=str(tick_id).encode("utf-8"),
        )
