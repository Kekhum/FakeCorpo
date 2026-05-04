"""Pure functions for the roaster temperature curve and sample generation.

A typical 12-min roast goes through:
  Phase 1 — charge drop:    0..30s    drum 220 -> 100 C  (beans absorb heat fast)
  Phase 2 — recovery:      30..360s   drum 100 -> 190 C  (Maillard development)
  Phase 3 — development:  360..720s   drum 190 -> 210 C  (first crack ~480s)

Exhaust temp tracks drum with ~20 C lag and small jitter.
Burner % stays high in Phase 2, drops in Phase 3.
Fan speed ramps up in Phase 3.

These are pure functions of `elapsed_sec` plus an `rng` for jitter, so they
unit-test cleanly without DB / Kafka / time machinery.
"""

import random
from datetime import datetime, timedelta
from typing import NamedTuple


class Sample(NamedTuple):
    elapsed_seconds: int
    drum_temp_celsius: float
    exhaust_temp_celsius: float
    fan_speed_pct: float
    burner_pct: float


def _interp(t: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * ((t - x0) / (x1 - x0))


def drum_temp(elapsed_sec: float, total_sec: int = 720) -> float:
    if elapsed_sec < 30:
        return _interp(elapsed_sec, 0, 30, 220.0, 100.0)
    if elapsed_sec < 360:
        return _interp(elapsed_sec, 30, 360, 100.0, 190.0)
    return _interp(elapsed_sec, 360, total_sec, 190.0, 210.0)


def burner_pct(elapsed_sec: float, total_sec: int = 720) -> float:
    # Aggressive in recovery, eased back in development.
    if elapsed_sec < 30:
        return 95.0
    if elapsed_sec < 360:
        return 90.0
    return _interp(elapsed_sec, 360, total_sec, 70.0, 50.0)


def fan_speed_pct(elapsed_sec: float, total_sec: int = 720) -> float:
    # Low at charge, ramping in development for evaporation.
    if elapsed_sec < 360:
        return 30.0
    return _interp(elapsed_sec, 360, total_sec, 35.0, 70.0)


def sample_at(
    elapsed_sec: int,
    rng: random.Random,
    total_sec: int = 720,
    drum_jitter: float = 1.5,
    exhaust_lag_c: float = 20.0,
) -> Sample:
    drum = drum_temp(elapsed_sec, total_sec) + rng.uniform(-drum_jitter, drum_jitter)
    exhaust = drum - exhaust_lag_c + rng.uniform(-1.0, 1.0)
    return Sample(
        elapsed_seconds=elapsed_sec,
        drum_temp_celsius=round(drum, 2),
        exhaust_temp_celsius=round(exhaust, 2),
        fan_speed_pct=round(fan_speed_pct(elapsed_sec, total_sec), 1),
        burner_pct=round(burner_pct(elapsed_sec, total_sec), 1),
    )


def samples_in_window(
    sim_started_at: datetime,
    from_sim_at: datetime,
    to_sim_at: datetime,
    interval_sec: int,
    total_sec: int,
    rng: random.Random,
) -> list[tuple[datetime, Sample]]:
    """Generate all samples whose elapsed offset falls in [from, to). Returned
    as (sim_at, Sample) pairs."""
    out: list[tuple[datetime, Sample]] = []
    if to_sim_at <= from_sim_at:
        return out

    from_elapsed = max(0, int((from_sim_at - sim_started_at).total_seconds()))
    to_elapsed = min(total_sec, int((to_sim_at - sim_started_at).total_seconds()))

    # Snap to interval grid so samples land at predictable seconds.
    first_tick = ((from_elapsed + interval_sec - 1) // interval_sec) * interval_sec
    if first_tick == from_elapsed and first_tick > 0:
        # Avoid emitting a sample we already emitted in the previous window.
        first_tick += interval_sec

    elapsed = first_tick
    while elapsed <= to_elapsed:
        sim_at = sim_started_at + timedelta(seconds=elapsed)
        out.append((sim_at, sample_at(elapsed, rng, total_sec=total_sec)))
        elapsed += interval_sec
    return out
