"""Pure-function weather generator. Each call deterministic given (rng, month, country)."""

import random


# Seasonal probability of each condition by month (1..12) for a generic
# Northern-European climate. Light tweaks per country in `weather_for_day`.
_BASE_PROBS: list[dict[str, float]] = [
    {"sunny": 0.20, "cloudy": 0.30, "rainy": 0.30, "snowy": 0.20},  # Jan
    {"sunny": 0.20, "cloudy": 0.30, "rainy": 0.30, "snowy": 0.20},  # Feb
    {"sunny": 0.30, "cloudy": 0.35, "rainy": 0.30, "snowy": 0.05},  # Mar
    {"sunny": 0.40, "cloudy": 0.30, "rainy": 0.30, "snowy": 0.0},   # Apr
    {"sunny": 0.50, "cloudy": 0.25, "rainy": 0.25, "snowy": 0.0},   # May
    {"sunny": 0.55, "cloudy": 0.25, "rainy": 0.20, "snowy": 0.0},   # Jun
    {"sunny": 0.60, "cloudy": 0.25, "rainy": 0.15, "snowy": 0.0},   # Jul
    {"sunny": 0.55, "cloudy": 0.25, "rainy": 0.20, "snowy": 0.0},   # Aug
    {"sunny": 0.45, "cloudy": 0.30, "rainy": 0.25, "snowy": 0.0},   # Sep
    {"sunny": 0.30, "cloudy": 0.35, "rainy": 0.35, "snowy": 0.0},   # Oct
    {"sunny": 0.20, "cloudy": 0.35, "rainy": 0.35, "snowy": 0.10},  # Nov
    {"sunny": 0.15, "cloudy": 0.30, "rainy": 0.30, "snowy": 0.25},  # Dec
]


# Monthly average temperature (°C) for a generic European city.
_BASE_TEMP_C: list[float] = [
    1, 2, 6, 11, 15, 19, 22, 22, 17, 12, 6, 2,
]


# Per-country tweaks: temperature offset (warmer south, colder north).
_COUNTRY_TEMP_OFFSET: dict[str, float] = {
    "IT": +5.0,
    "GB": +1.0,
    "NL": +0.0,
    "DE": -1.0,
    "DK": -1.5,
    "SE": -3.0,
    "NO": -3.5,
    "PL": -1.0,
    "CZ": -1.0,
    "SK": -0.5,
}


# Per-country snowy bias: Mediterranean cafés (Italy) almost never see snow.
_COUNTRY_SNOW_DAMPING: dict[str, float] = {
    "IT": 0.10,   # nearly never snows
    "GB": 0.40,
    "NL": 0.50,
    "DE": 0.80,
    "DK": 0.90,
    "SE": 1.30,
    "NO": 1.40,
    "PL": 1.10,
    "CZ": 1.10,
    "SK": 1.10,
}


def weather_for_day(
    month: int,
    country: str,
    rng: random.Random,
) -> tuple[str, float]:
    """Returns (condition, temperature_celsius)."""
    probs = dict(_BASE_PROBS[month - 1])

    # Apply country snow damping; redistribute removed mass to cloudy/sunny
    snow_factor = _COUNTRY_SNOW_DAMPING.get(country, 1.0)
    snow_orig = probs["snowy"]
    probs["snowy"] = round(snow_orig * snow_factor, 4)
    if probs["snowy"] > snow_orig:
        delta = probs["snowy"] - snow_orig
        probs["cloudy"] = max(0.0, probs["cloudy"] - delta * 0.5)
        probs["sunny"]  = max(0.0, probs["sunny"]  - delta * 0.5)
    elif probs["snowy"] < snow_orig:
        delta = snow_orig - probs["snowy"]
        probs["cloudy"] += delta * 0.5
        probs["sunny"]  += delta * 0.5
    # Renormalize
    total = sum(probs.values())
    probs = {k: v / total for k, v in probs.items()}

    r = rng.random()
    cum = 0.0
    chosen = "cloudy"
    for k, p in probs.items():
        cum += p
        if r < cum:
            chosen = k
            break

    base_t = _BASE_TEMP_C[month - 1] + _COUNTRY_TEMP_OFFSET.get(country, 0.0)
    # Add daily noise + adjustments per condition
    noise = rng.uniform(-3.0, 3.0)
    t = base_t + noise
    if chosen == "snowy":
        t = min(t, 0.5)
    elif chosen == "rainy":
        t -= 2.0
    elif chosen == "sunny":
        t += 2.0
    return chosen, round(t, 1)
