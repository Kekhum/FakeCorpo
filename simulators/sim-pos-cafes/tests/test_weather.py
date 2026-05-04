import random
from collections import Counter

from sim_pos_cafes.weather import weather_for_day


def test_january_in_italy_rarely_snows():
    rng = random.Random(2026)
    n = 500
    conditions = Counter(weather_for_day(1, "IT", rng)[0] for _ in range(n))
    assert conditions["snowy"] < 0.05 * n


def test_january_in_norway_snows_often():
    rng = random.Random(2026)
    n = 500
    conditions = Counter(weather_for_day(1, "NO", rng)[0] for _ in range(n))
    assert conditions["snowy"] >= 0.10 * n


def test_july_temperature_warm_in_italy_cooler_in_norway():
    rng = random.Random(0)
    n = 200
    italy = [weather_for_day(7, "IT", rng)[1] for _ in range(n)]
    rng = random.Random(0)
    norway = [weather_for_day(7, "NO", rng)[1] for _ in range(n)]
    assert sum(italy) / n > sum(norway) / n


def test_snowy_days_have_freezing_temperature():
    rng = random.Random(2026)
    for _ in range(200):
        condition, temp = weather_for_day(1, "PL", rng)
        if condition == "snowy":
            assert temp <= 0.5


def test_july_never_snows_anywhere():
    rng = random.Random(2026)
    countries = ["IT", "GB", "NL", "DE", "DK", "SE", "NO", "PL", "CZ", "SK"]
    for country in countries:
        conditions = [weather_for_day(7, country, rng)[0] for _ in range(50)]
        assert "snowy" not in conditions
