import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from fakecorpo_shared.schemas.clock import ClockState

from .config import Settings
from .state import init_state_if_missing, load_state, save_state
from .ticker import Ticker


class _AppState:
    settings: Settings
    redis: Redis
    producer: AIOKafkaProducer
    ticker: Ticker


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("orchestrator_clock")
    log.info("startup settings=%s", settings.model_dump(exclude={"redis_url"}))

    redis = Redis.from_url(settings.redis_url)
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
    await producer.start()

    initial = ClockState(
        sim_time=settings.initial_sim_time,
        speed_ratio=settings.initial_speed_ratio,
        paused=False,
        updated_at=datetime.now(timezone.utc),
    )
    persisted = await init_state_if_missing(redis, initial)
    log.info("startup.clock_state sim_time=%s speed=%d paused=%s",
             persisted.sim_time.isoformat(), persisted.speed_ratio, persisted.paused)

    ticker = Ticker(settings, redis, producer)
    await ticker.start()

    _state.settings = settings
    _state.redis = redis
    _state.producer = producer
    _state.ticker = ticker

    try:
        yield
    finally:
        log.info("shutdown")
        await ticker.stop()
        await producer.stop()
        await redis.aclose()


app = FastAPI(title="FakeCorpo Orchestrator Clock", version="0.1.0", lifespan=lifespan)


class SpeedBody(BaseModel):
    speed_ratio: int = Field(ge=1, description="Sim seconds per real second.")


class SeekBody(BaseModel):
    sim_time: datetime


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/clock/state", response_model=ClockState)
async def get_state() -> ClockState:
    state = await load_state(_state.redis)
    if state is None:
        raise HTTPException(status_code=503, detail="clock not initialized yet")
    return state


async def _mutate(update: dict) -> ClockState:
    state = await load_state(_state.redis)
    if state is None:
        raise HTTPException(status_code=503, detail="clock not initialized yet")
    new_state = state.model_copy(
        update={**update, "updated_at": datetime.now(timezone.utc)}
    )
    await save_state(_state.redis, new_state)
    return new_state


@app.post("/clock/pause", response_model=ClockState)
async def pause() -> ClockState:
    return await _mutate({"paused": True})


@app.post("/clock/resume", response_model=ClockState)
async def resume() -> ClockState:
    return await _mutate({"paused": False})


@app.post("/clock/speed", response_model=ClockState)
async def set_speed(body: SpeedBody) -> ClockState:
    return await _mutate({"speed_ratio": body.speed_ratio})


@app.post("/clock/seek", response_model=ClockState)
async def seek(body: SeekBody) -> ClockState:
    target = body.sim_time
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return await _mutate({"sim_time": target})
