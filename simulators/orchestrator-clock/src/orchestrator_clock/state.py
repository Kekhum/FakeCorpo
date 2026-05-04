from redis.asyncio import Redis

from fakecorpo_shared.schemas.clock import ClockState

STATE_KEY = "clock:state"
TICK_ID_KEY = "clock:tick_id"


async def load_state(redis: Redis) -> ClockState | None:
    raw = await redis.get(STATE_KEY)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return ClockState.model_validate_json(raw)


async def save_state(redis: Redis, state: ClockState) -> None:
    await redis.set(STATE_KEY, state.model_dump_json())


async def init_state_if_missing(redis: Redis, initial: ClockState) -> ClockState:
    existing = await load_state(redis)
    if existing is not None:
        return existing
    await save_state(redis, initial)
    return initial


async def next_tick_id(redis: Redis) -> int:
    return await redis.incr(TICK_ID_KEY)
