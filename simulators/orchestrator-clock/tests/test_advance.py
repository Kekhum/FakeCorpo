from datetime import datetime, timedelta, timezone

from fakecorpo_shared.schemas.clock import ClockState, advance


def _state(speed: int = 60, paused: bool = False) -> ClockState:
    t = datetime(2022, 1, 1, tzinfo=timezone.utc)
    return ClockState(sim_time=t, speed_ratio=speed, paused=paused, updated_at=t)


def test_advance_moves_sim_time_by_speed_ratio_seconds():
    s = _state(speed=60)
    after = advance(s, real_seconds_elapsed=1.0)
    assert after.sim_time - s.sim_time == timedelta(seconds=60)


def test_advance_respects_fractional_real_seconds():
    s = _state(speed=288)
    after = advance(s, real_seconds_elapsed=0.5)
    assert after.sim_time - s.sim_time == timedelta(seconds=144)


def test_advance_does_nothing_when_paused():
    s = _state(speed=86400, paused=True)
    after = advance(s, real_seconds_elapsed=10.0)
    assert after.sim_time == s.sim_time
    assert after.updated_at >= s.updated_at


def test_advance_one_day_per_5min_for_300_real_seconds():
    s = _state(speed=288)
    after = advance(s, real_seconds_elapsed=300.0)
    assert after.sim_time - s.sim_time == timedelta(days=1)
