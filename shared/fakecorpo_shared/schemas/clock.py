from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, field_validator


class ClockState(BaseModel):
    """Authoritative state of the simulation clock — persisted in Redis."""

    sim_time: datetime = Field(
        description="Current simulated wall-clock time (UTC).",
    )
    speed_ratio: int = Field(
        ge=1,
        description="How many sim seconds elapse per real second. 288 = 1 sim day per 5 real min.",
    )
    paused: bool = Field(
        default=False,
        description="If true, sim_time stops advancing (heartbeat ticks still publish).",
    )
    updated_at: datetime = Field(
        description="Real wall-clock time (UTC) of last state update.",
    )

    @field_validator("sim_time", "updated_at")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class ClockTick(BaseModel):
    """Heartbeat event published to Kafka topic `clock.tick` every real second."""

    tick_id: int = Field(ge=1, description="Monotonic counter, starts at 1.")
    sim_time: datetime
    real_time: datetime
    speed_ratio: int = Field(ge=1)
    paused: bool

    @field_validator("sim_time", "real_time")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


def advance(state: ClockState, real_seconds_elapsed: float) -> ClockState:
    """Pure function: advance sim_time by `real_seconds_elapsed * speed_ratio`.

    No-op if paused. Always refreshes `updated_at` to now (UTC).
    """
    now_utc = datetime.now(timezone.utc)
    if state.paused:
        return state.model_copy(update={"updated_at": now_utc})
    sim_delta = timedelta(seconds=real_seconds_elapsed * state.speed_ratio)
    return state.model_copy(
        update={
            "sim_time": state.sim_time + sim_delta,
            "updated_at": now_utc,
        }
    )
