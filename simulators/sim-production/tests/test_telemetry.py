import random
from datetime import datetime, timedelta, timezone

from sim_production.telemetry import (
    burner_pct,
    drum_temp,
    fan_speed_pct,
    sample_at,
    samples_in_window,
)


def test_drum_temp_drops_at_charge_then_recovers():
    assert drum_temp(0) == 220.0
    assert 99 <= drum_temp(30) <= 101
    # Recovery zone is monotonic
    earlier = drum_temp(60)
    later = drum_temp(300)
    assert earlier < later
    # End is around 210
    assert 209 <= drum_temp(720, total_sec=720) <= 211


def test_burner_drops_after_first_crack_zone():
    # Phase 2 (recovery) is high
    assert burner_pct(200) >= 85.0
    # Phase 3 starts dropping
    assert burner_pct(700) < burner_pct(360)


def test_fan_speed_climbs_in_development_phase():
    assert fan_speed_pct(100) <= fan_speed_pct(700)


def test_sample_includes_jitter_but_stays_close_to_curve():
    rng = random.Random(0)
    # Drum at 200s should be in the recovery range
    s = sample_at(200, rng)
    assert 100 <= s.drum_temp_celsius <= 200
    assert s.exhaust_temp_celsius < s.drum_temp_celsius
    assert 0 <= s.fan_speed_pct <= 100
    assert 0 <= s.burner_pct <= 100


def test_samples_in_window_emits_only_inside_window():
    started = datetime(2022, 1, 1, tzinfo=timezone.utc)
    rng = random.Random(0)
    out = samples_in_window(
        sim_started_at=started,
        from_sim_at=started + timedelta(seconds=100),
        to_sim_at=started + timedelta(seconds=200),
        interval_sec=10,
        total_sec=720,
        rng=rng,
    )
    elapsed = [s.elapsed_seconds for _, s in out]
    assert all(100 <= e <= 200 for e in elapsed)
    assert elapsed == sorted(elapsed)
    # Spaced by interval
    diffs = {b - a for a, b in zip(elapsed, elapsed[1:])}
    assert diffs == {10}


def test_samples_in_window_does_not_double_emit_at_boundary():
    """Calling twice with adjacent windows shouldn't repeat the samples
    that landed exactly on the prior `to_sim_at`."""
    started = datetime(2022, 1, 1, tzinfo=timezone.utc)
    rng = random.Random(0)
    first = samples_in_window(
        sim_started_at=started,
        from_sim_at=started,
        to_sim_at=started + timedelta(seconds=100),
        interval_sec=10, total_sec=720, rng=rng,
    )
    second = samples_in_window(
        sim_started_at=started,
        from_sim_at=started + timedelta(seconds=100),
        to_sim_at=started + timedelta(seconds=200),
        interval_sec=10, total_sec=720, rng=rng,
    )
    elapsed_first = {s.elapsed_seconds for _, s in first}
    elapsed_second = {s.elapsed_seconds for _, s in second}
    assert not (elapsed_first & elapsed_second), (
        f"overlap at boundary: {elapsed_first & elapsed_second}"
    )


def test_samples_clip_to_total_sec():
    started = datetime(2022, 1, 1, tzinfo=timezone.utc)
    rng = random.Random(0)
    out = samples_in_window(
        sim_started_at=started,
        from_sim_at=started + timedelta(seconds=700),
        to_sim_at=started + timedelta(seconds=10_000),  # way past total
        interval_sec=10, total_sec=720, rng=rng,
    )
    assert all(s.elapsed_seconds <= 720 for _, s in out)
