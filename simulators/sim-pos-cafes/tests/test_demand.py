import math
import random
from collections import Counter
from datetime import datetime

from sim_pos_cafes.demand import (
    category_mix,
    day_of_week_multiplier,
    expected_hourly_rate,
    hour_of_day_multiplier,
    pick_category,
    sample_count,
    season_multiplier,
    weather_multiplier,
)


# ---------------------------- hour curves ----------------------------

def test_office_cafe_peaks_at_morning_and_lunch_not_evening():
    assert hour_of_day_multiplier(8, "office") > hour_of_day_multiplier(20, "office")
    assert hour_of_day_multiplier(12, "office") > hour_of_day_multiplier(20, "office")


def test_tourist_cafe_evening_strong_relative_to_office():
    # Tourist café at 19:00 has more activity than an office café at 19:00
    assert hour_of_day_multiplier(19, "tourist") > hour_of_day_multiplier(19, "office")


def test_all_curves_are_zero_at_midnight():
    for t in ("office", "tourist", "hipster", "transit"):
        assert hour_of_day_multiplier(0, t) == 0
        assert hour_of_day_multiplier(3, t) == 0


# ---------------------------- weekday curves ----------------------------

def test_office_cafe_weekend_dip():
    # Office: weekend (Sat=5, Sun=6) much lower than weekdays
    weekday_avg = sum(day_of_week_multiplier(d, "office") for d in range(0, 5)) / 5
    weekend_avg = sum(day_of_week_multiplier(d, "office") for d in range(5, 7)) / 2
    assert weekend_avg < weekday_avg * 0.6


def test_tourist_cafe_weekend_peak():
    weekend_avg = sum(day_of_week_multiplier(d, "tourist") for d in range(5, 7)) / 2
    weekday_avg = sum(day_of_week_multiplier(d, "tourist") for d in range(0, 5)) / 5
    assert weekend_avg > weekday_avg


# ---------------------------- season + weather ----------------------------

def test_summer_dip_winter_peak():
    assert season_multiplier(7) < season_multiplier(12)


def test_weather_rain_dampens_traffic():
    assert weather_multiplier("rainy") < weather_multiplier("cloudy")


def test_weather_snow_dampens_more_than_rain():
    assert weather_multiplier("snowy") < weather_multiplier("rainy")


def test_weather_unknown_falls_back_to_neutral():
    assert weather_multiplier("hailstorm") == 1.0


# ---------------------------- expected_hourly_rate ----------------------------

def test_expected_rate_zero_at_closed_hour_via_hour_curve():
    rate = expected_hourly_rate(
        baseline=20.0,
        hour=3,            # café closed
        weekday=2,
        month=6,
        cafe_type="office",
        weather_condition="sunny",
    )
    assert rate == 0


def test_expected_rate_realistic_size_at_peak():
    rate = expected_hourly_rate(
        baseline=25.0,
        hour=8,
        weekday=2,    # Wed
        month=11,     # November (peak season)
        cafe_type="office",
        weather_condition="sunny",
    )
    # baseline 25 * hour ~0.85 * weekday 1.10 * season 1.10 * weather 1.10 ~ ~28
    assert 20 < rate < 35


# ---------------------------- sample_count ----------------------------

def test_sample_count_zero_for_zero_rate():
    rng = random.Random(0)
    assert sample_count(0.0, rng) == 0


def test_sample_count_close_to_rate_in_expectation():
    rng = random.Random(42)
    n = 1000
    rate = 10.0
    samples = [sample_count(rate, rng) for _ in range(n)]
    mean = sum(samples) / n
    # Within 10% of rate at this sample size
    assert abs(mean - rate) < rate * 0.10


# ---------------------------- category_mix ----------------------------

def test_category_mix_sums_to_one_at_every_hour():
    for h in range(24):
        for is_summer in (True, False):
            s = sum(category_mix(h, is_summer).values())
            assert math.isclose(s, 1.0, abs_tol=1e-6), f"hour={h} summer={is_summer} sums to {s}"


def test_summer_shifts_some_hot_to_iced():
    winter = category_mix(15, is_summer=False)
    summer = category_mix(15, is_summer=True)
    assert summer["coffee_iced"] > winter["coffee_iced"]
    assert summer["coffee_hot"] < winter["coffee_hot"]


def test_pick_category_distribution_follows_mix():
    rng = random.Random(2026)
    n = 5000
    counts = Counter(pick_category(8, is_summer=False, rng=rng) for _ in range(n))
    # At 8am, hot coffee should dominate
    assert counts["coffee_hot"] > 0.5 * n
