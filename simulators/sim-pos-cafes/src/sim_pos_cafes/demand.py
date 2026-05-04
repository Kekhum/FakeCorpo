"""Pure functions for the demand model.

Hourly transaction count for a café = baseline_hourly_traffic
                                       × hour_of_day(hour, type)
                                       × day_of_week(weekday, type)
                                       × season(month, type)
                                       × weather(condition).

All multipliers are pure (deterministic given inputs). The only randomness
is in the final integer sample, which is a simple Gaussian approximation
of a Poisson — fine for our rates of 1-50 expected events/hour.
"""

import math
import random


# Categories that menu picks fall into.
CATEGORIES = ("coffee_hot", "coffee_iced", "food", "retail")


# ---------------------------- hour_of_day ----------------------------

# Indexed [hour] returning multiplier of "peak hour" rate.
# Peak = 1.0; off-hours = 0.0 (closed window handled separately).
# Different curves per cafe_type.
_HOUR_CURVES: dict[str, list[float]] = {
    "office":  [0,0,0,0,0, 0,0.20,0.85,1.00,0.60, 0.45,0.55,0.95,0.80,0.50, 0.40,0.35,0.30,0.10, 0.0,0,0,0,0],
    "tourist": [0,0,0,0,0, 0,0.0, 0.30,0.55,0.75, 0.85,0.95,1.00,0.95,0.90, 0.85,0.80,0.75,0.60, 0.45,0.30,0.0,0,0],
    "hipster": [0,0,0,0,0, 0,0.0, 0.0, 0.45,0.70, 0.85,0.95,1.00,0.95,0.90, 0.95,0.90,0.80,0.65, 0.45,0.20,0.0,0,0],
    "transit": [0,0,0,0,0, 0,0.65,1.00,0.95,0.55, 0.40,0.50,0.70,0.55,0.40, 0.45,0.70,0.90,0.80, 0.50,0.25,0.10,0,0],
}


def hour_of_day_multiplier(hour: int, cafe_type: str) -> float:
    return _HOUR_CURVES.get(cafe_type, _HOUR_CURVES["office"])[hour]


# ---------------------------- day_of_week ----------------------------
# 0=Mon ... 6=Sun
_WEEKDAY_CURVES: dict[str, list[float]] = {
    "office":  [1.10, 1.10, 1.10, 1.10, 1.00, 0.40, 0.30],
    "tourist": [0.85, 0.85, 0.90, 0.95, 1.05, 1.30, 1.25],
    "hipster": [0.90, 0.90, 0.95, 1.00, 1.10, 1.20, 1.10],
    "transit": [1.05, 1.05, 1.05, 1.05, 1.10, 0.80, 0.70],
}


def day_of_week_multiplier(weekday: int, cafe_type: str) -> float:
    return _WEEKDAY_CURVES.get(cafe_type, _WEEKDAY_CURVES["office"])[weekday]


# ---------------------------- season ----------------------------
# month: 1..12 (Jan..Dec)
_SEASON_CURVE: list[float] = [
    # Jan  Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
    1.05, 1.05, 1.00, 1.00, 1.00, 0.95, 0.85, 0.85, 1.00, 1.05, 1.10, 1.15,
]


def season_multiplier(month: int) -> float:
    return _SEASON_CURVE[month - 1]


# ---------------------------- weather ----------------------------
_WEATHER_MULTIPLIER: dict[str, float] = {
    "sunny":  1.10,
    "cloudy": 1.00,
    "rainy":  0.75,
    "snowy":  0.55,
}


def weather_multiplier(condition: str) -> float:
    return _WEATHER_MULTIPLIER.get(condition, 1.0)


# ---------------------------- expected count + sampling ----------------------------

def expected_hourly_rate(
    baseline: float,
    hour: int,
    weekday: int,
    month: int,
    cafe_type: str,
    weather_condition: str,
) -> float:
    """Combined expected transaction count for one (café, hour) bucket."""
    return (
        baseline
        * hour_of_day_multiplier(hour, cafe_type)
        * day_of_week_multiplier(weekday, cafe_type)
        * season_multiplier(month)
        * weather_multiplier(weather_condition)
    )


def sample_count(rate: float, rng: random.Random) -> int:
    """Gaussian approximation of Poisson(rate). Adequate for rate >= 1."""
    if rate <= 0:
        return 0
    if rate < 1.0:
        # Bernoulli-ish for small rates: probability ~ rate
        return 1 if rng.random() < rate else 0
    sample = rng.gauss(rate, math.sqrt(rate))
    return max(0, int(round(sample)))


# ---------------------------- category mix ----------------------------
# Returns probabilities for each category given hour and "is_summer".
# Sum to 1.0.
def category_mix(hour: int, is_summer: bool) -> dict[str, float]:
    if hour < 6 or hour >= 22:
        # Edge hours: mostly hot coffee
        base = {"coffee_hot": 0.70, "coffee_iced": 0.05, "food": 0.20, "retail": 0.05}
    elif hour < 11:
        # Morning: hot coffee + some food
        base = {"coffee_hot": 0.65, "coffee_iced": 0.05, "food": 0.25, "retail": 0.05}
    elif hour < 14:
        # Lunch: more food
        base = {"coffee_hot": 0.40, "coffee_iced": 0.10, "food": 0.45, "retail": 0.05}
    elif hour < 18:
        # Afternoon: coffee + retail bag pickup
        base = {"coffee_hot": 0.55, "coffee_iced": 0.15, "food": 0.20, "retail": 0.10}
    else:
        # Evening: coffee + food
        base = {"coffee_hot": 0.50, "coffee_iced": 0.10, "food": 0.35, "retail": 0.05}

    if is_summer:
        # Shift some hot to iced
        base = dict(base)
        shift = min(0.20, base["coffee_hot"] * 0.30)
        base["coffee_hot"] -= shift
        base["coffee_iced"] += shift
    return base


def pick_category(hour: int, is_summer: bool, rng: random.Random) -> str:
    mix = category_mix(hour, is_summer)
    r = rng.random()
    cum = 0.0
    for cat, p in mix.items():
        cum += p
        if r < cum:
            return cat
    return "coffee_hot"
