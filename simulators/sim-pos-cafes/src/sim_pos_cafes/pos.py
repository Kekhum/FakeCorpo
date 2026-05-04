import logging
import random
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fakecorpo_shared.schemas.pos import (
    TransactionCompleted,
    TransactionLineCompleted,
)

from .config import Settings
from .demand import (
    expected_hourly_rate,
    pick_category,
    sample_count,
)
from .events import EventPublisher
from .models import Cafe, DailyWeather, MenuItem, Transaction, TransactionLine
from .weather import weather_for_day

log = logging.getLogger(__name__)


# =====================================================================
# Helpers — load master data once per sim-hour batch
# =====================================================================


async def load_cafes(session: AsyncSession) -> list[Cafe]:
    return list((await session.scalars(select(Cafe))).all())


async def load_menu_items_by_brand_category(
    session: AsyncSession,
) -> dict[tuple[str, str], list[MenuItem]]:
    items = list((await session.scalars(select(MenuItem))).all())
    by_key: dict[tuple[str, str], list[MenuItem]] = defaultdict(list)
    for it in items:
        by_key[(it.brand, it.category)].append(it)
    return by_key


# =====================================================================
# Weather caching: one row per (cafe_id, sim_date)
# =====================================================================


async def get_or_create_weather(
    session: AsyncSession,
    cafe: Cafe,
    sim_date: date,
    rng: random.Random,
) -> DailyWeather:
    existing = (
        await session.scalars(
            select(DailyWeather)
            .where(DailyWeather.cafe_id == cafe.id)
            .where(DailyWeather.sim_date == sim_date)
        )
    ).one_or_none()
    if existing is not None:
        return existing

    condition, temp = weather_for_day(sim_date.month, cafe.country, rng)
    row = DailyWeather(
        cafe_id=cafe.id,
        sim_date=sim_date,
        condition=condition,
        temperature_celsius=temp,
    )
    session.add(row)
    await session.flush()
    return row


# =====================================================================
# Transaction generation for one (café, sim-hour)
# =====================================================================


def _is_summer(month: int) -> bool:
    return month in (6, 7, 8)


def _txn_number(cafe_code: str, sim_at: datetime, seq: int) -> str:
    return f"{cafe_code}-{sim_at:%Y%m%d}-{sim_at.hour:02d}-{seq:04d}"


async def _process_one_hour(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng_demand: random.Random,
    rng_weather: random.Random,
    rng_picks: random.Random,
    cafe: Cafe,
    sim_hour: datetime,
    items_by_brand_cat: dict[tuple[str, str], list[MenuItem]],
) -> int:
    """Generate transactions for this café for this specific sim-hour. Returns count."""
    if sim_hour.hour < cafe.opening_hour or sim_hour.hour >= cafe.closing_hour:
        return 0

    weather = await get_or_create_weather(session, cafe, sim_hour.date(), rng_weather)

    rate = expected_hourly_rate(
        baseline=cafe.baseline_hourly_traffic,
        hour=sim_hour.hour,
        weekday=sim_hour.weekday(),
        month=sim_hour.month,
        cafe_type=cafe.cafe_type,
        weather_condition=weather.condition,
    )
    n = sample_count(rate, rng_demand)
    if n == 0:
        return 0

    is_summer = _is_summer(sim_hour.month)
    events_to_publish: list[TransactionCompleted] = []

    for seq in range(1, n + 1):
        # Place each transaction at a random minute within the sim-hour
        offset = timedelta(minutes=rng_demand.randint(0, 59), seconds=rng_demand.randint(0, 59))
        sim_at = sim_hour + offset

        # 1-2 items, mostly 1
        n_lines = 1 if rng_picks.random() < 0.75 else 2
        item_count_total = 0
        total_eur = 0.0
        line_records: list[tuple[MenuItem, int, float, float]] = []
        chosen_categories: set[str] = set()

        for _ in range(n_lines):
            cat = pick_category(sim_hour.hour, is_summer, rng_picks)
            # Avoid duplicate category in same transaction (variety)
            if cat in chosen_categories and len(chosen_categories) < 3:
                cat = pick_category(sim_hour.hour, is_summer, rng_picks)
            chosen_categories.add(cat)

            candidates = items_by_brand_cat.get((cafe.brand, cat))
            if not candidates:
                # Fallback to coffee_hot for that brand
                candidates = items_by_brand_cat.get((cafe.brand, "coffee_hot"))
            if not candidates:
                continue
            item = rng_picks.choice(candidates)
            qty = 1 if rng_picks.random() < 0.92 else 2
            line_total = round(item.price_eur * qty, 2)
            line_records.append((item, qty, item.price_eur, line_total))
            item_count_total += qty
            total_eur += line_total

        if not line_records:
            continue

        total_eur = round(total_eur, 2)
        payment = "card" if rng_demand.random() < settings.payment_card_share else "cash"

        txn = Transaction(
            transaction_number=_txn_number(cafe.code, sim_at, seq),
            cafe_id=cafe.id,
            sim_at=sim_at,
            payment_method=payment,
            item_count=item_count_total,
            total_eur=total_eur,
        )
        session.add(txn)
        await session.flush()

        for item, qty, unit_price, line_total in line_records:
            session.add(
                TransactionLine(
                    transaction_id=txn.id,
                    menu_item_id=item.id,
                    quantity=qty,
                    unit_price_eur=unit_price,
                    line_total_eur=line_total,
                )
            )

        events_to_publish.append(
            TransactionCompleted(
                transaction_id=txn.id,
                transaction_number=txn.transaction_number,
                cafe_code=cafe.code,
                cafe_name=cafe.name,
                brand=cafe.brand,
                sim_at=sim_at,
                payment_method=payment,  # type: ignore[arg-type]
                item_count=item_count_total,
                total_eur=total_eur,
                lines=[
                    TransactionLineCompleted(
                        menu_item_code=item.code,
                        menu_item_name=item.name,
                        category=item.category,
                        quantity=qty,
                        unit_price_eur=unit_price,
                        line_total_eur=line_total,
                    )
                    for item, qty, unit_price, line_total in line_records
                ],
                weather_condition=weather.condition,
                weather_temp_celsius=weather.temperature_celsius,
            )
        )

    # Flush everything for this hour, then publish (DB authoritative).
    await session.flush()
    for ev in events_to_publish:
        await publisher.publish_transaction(ev)
    return len(events_to_publish)


async def process_sim_hour(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng_demand: random.Random,
    rng_weather: random.Random,
    rng_picks: random.Random,
    sim_hour: datetime,
) -> int:
    """Generate transactions across ALL cafés for this sim-hour."""
    cafes = await load_cafes(session)
    items_by_brand_cat = await load_menu_items_by_brand_category(session)

    total = 0
    for cafe in cafes:
        total += await _process_one_hour(
            session, publisher, settings,
            rng_demand, rng_weather, rng_picks,
            cafe, sim_hour, items_by_brand_cat,
        )
    log.info("pos.hour_processed sim_hour=%s txns=%d", sim_hour.isoformat(), total)
    return total
