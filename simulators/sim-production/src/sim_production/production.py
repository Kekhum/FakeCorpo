import logging
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fakecorpo_shared.schemas.procurement import PurchaseOrderArrived
from fakecorpo_shared.schemas.production import (
    BatchCompleted,
    BatchInputItem,
    BatchStarted,
    RoasterTelemetry,
)

from .config import Settings
from .events import EventPublisher
from .models import (
    BatchInput,
    BlendRecipe,
    GreenInventory,
    GreenInventoryMovement,
    RoastedInventory,
    RoastedSku,
    RoastingBatch,
)
from .seed_data import REJECTION_REASONS
from .telemetry import samples_in_window

log = logging.getLogger(__name__)


# =====================================================================
# Arrivals -> green inventory
# =====================================================================


async def apply_arrival(
    session: AsyncSession,
    event: PurchaseOrderArrived,
    sim_now: datetime,
) -> None:
    """Credit accepted green coffee from a settled PO. Skips zero-quantity
    lines (lost shipments / rejected lots)."""
    if event.arrival_status == "lost":
        return
    if not event.lines:
        log.warning("arrival.no_lines po=%s — cannot credit inventory", event.po_number)
        return

    sim_at = event.sim_actual_arrival or sim_now

    for line in event.lines:
        if line.quantity_accepted_kg <= 0:
            continue
        await _credit_green(
            session=session,
            variety_code=line.variety_code,
            quantity_kg=line.quantity_accepted_kg,
            sim_at=sim_at,
            source_po_id=event.po_id,
            source_po_number=event.po_number,
        )

    log.info(
        "arrival.applied po=%s status=%s lines_credited=%d total_kg=%.1f",
        event.po_number, event.arrival_status,
        sum(1 for l in event.lines if l.quantity_accepted_kg > 0),
        event.quantity_accepted_kg,
    )


async def _credit_green(
    session: AsyncSession,
    variety_code: str,
    quantity_kg: float,
    sim_at: datetime,
    source_po_id: int,
    source_po_number: str,
) -> None:
    inv = (
        await session.scalars(
            select(GreenInventory).where(GreenInventory.variety_code == variety_code)
        )
    ).one_or_none()
    if inv is None:
        inv = GreenInventory(
            variety_code=variety_code,
            quantity_kg=0.0,
            last_updated_sim_time=sim_at,
        )
        session.add(inv)
        await session.flush()
    inv.quantity_kg = round(inv.quantity_kg + quantity_kg, 2)
    inv.last_updated_sim_time = sim_at

    session.add(
        GreenInventoryMovement(
            variety_code=variety_code,
            quantity_kg_delta=quantity_kg,
            movement_type="arrival",
            source_po_id=source_po_id,
            source_po_number=source_po_number,
            sim_at=sim_at,
        )
    )


# =====================================================================
# Roasting decision: what to start, when
# =====================================================================


def _batch_number(sim_now: datetime, seq: int) -> str:
    return f"BATCH-{sim_now:%Y%m%d}-{seq:04d}"


def _planned_input_for_target(
    target_output_kg: float, settings: Settings
) -> float:
    """We over-charge the roaster by ~mean weight loss to land near target output."""
    return round(target_output_kg / (1.0 - settings.weight_loss_mean), 1)


async def _all_skus_with_recipes(
    session: AsyncSession,
) -> list[tuple[RoastedSku, list[BlendRecipe]]]:
    skus = (await session.scalars(select(RoastedSku))).all()
    recipes_rows = (await session.scalars(select(BlendRecipe))).all()
    by_sku: dict[int, list[BlendRecipe]] = defaultdict(list)
    for r in recipes_rows:
        by_sku[r.sku_id].append(r)
    return [(sku, by_sku.get(sku.id, [])) for sku in skus]


async def _read_green_levels(
    session: AsyncSession,
) -> dict[str, float]:
    rows = (
        await session.execute(
            select(GreenInventory.variety_code, GreenInventory.quantity_kg)
        )
    ).all()
    return {code: qty for code, qty in rows}


async def _next_batch_seq_for_day(
    session: AsyncSession, sim_now: datetime
) -> int:
    prefix = f"BATCH-{sim_now:%Y%m%d}-"
    count = (
        await session.scalar(
            select(func.count(RoastingBatch.id))
            .where(RoastingBatch.batch_number.like(prefix + "%"))
        )
    ) or 0
    return int(count) + 1


async def maybe_start_batches(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng: random.Random,
    sim_now: datetime,
) -> list[BatchStarted]:
    """Decide how many batches to start today, pick SKUs, deduct inventory,
    create batch rows, publish events. Skips SKUs without enough green stock."""
    skus_with_recipes = await _all_skus_with_recipes(session)
    skus_with_recipes = [(s, r) for s, r in skus_with_recipes if r]
    if not skus_with_recipes:
        log.warning("roasting.no_skus_with_recipes — did seeding run?")
        return []

    n_batches = rng.randint(settings.min_batches_per_day, settings.max_batches_per_day)
    rng.shuffle(skus_with_recipes)
    started: list[BatchStarted] = []
    starting_seq = await _next_batch_seq_for_day(session, sim_now)

    levels = await _read_green_levels(session)

    # Try each SKU until we've started n_batches or exhausted candidates.
    sku_pool = list(skus_with_recipes)
    while sku_pool and len(started) < n_batches:
        sku, recipe = sku_pool.pop()

        target_output = float(rng.randint(settings.batch_size_min_kg, settings.batch_size_max_kg))
        planned_input = _planned_input_for_target(target_output, settings)

        per_variety = {
            r.variety_code: round(planned_input * r.percentage, 2) for r in recipe
        }
        # Inventory check
        if not all(levels.get(v, 0.0) >= q for v, q in per_variety.items()):
            log.info(
                "roasting.skip_insufficient sku=%s needed=%s have=%s",
                sku.code, per_variety,
                {v: levels.get(v, 0.0) for v in per_variety},
            )
            continue

        # Deduct in our local levels copy AND in DB
        batch = RoastingBatch(
            batch_number=_batch_number(sim_now, starting_seq + len(started)),
            sku_id=sku.id,
            sim_started_at=sim_now,
            sim_completed_at=None,
            last_telemetry_sim_at=None,
            planned_input_kg=planned_input,
            status="in_progress",
        )
        session.add(batch)
        await session.flush()

        for variety_code, qty in per_variety.items():
            levels[variety_code] = round(levels[variety_code] - qty, 2)
            await _debit_green(
                session=session,
                variety_code=variety_code,
                quantity_kg=qty,
                sim_at=sim_now,
                source_batch_id=batch.id,
            )
            session.add(
                BatchInput(batch_id=batch.id, variety_code=variety_code, quantity_kg=qty)
            )

        event = BatchStarted(
            batch_id=batch.id,
            batch_number=batch.batch_number,
            sku_code=sku.code,
            sku_name=sku.name,
            brand=sku.brand,
            sim_started_at=sim_now,
            planned_input_kg=planned_input,
            lines=[
                BatchInputItem(variety_code=v, quantity_kg=q)
                for v, q in per_variety.items()
            ],
        )
        await publisher.publish_batch_started(event)
        started.append(event)

    log.info(
        "roasting.day_done sim_now=%s started=%d skipped_due_to_inventory=%d",
        sim_now.isoformat(), len(started),
        n_batches - len(started),
    )
    return started


async def _debit_green(
    session: AsyncSession,
    variety_code: str,
    quantity_kg: float,
    sim_at: datetime,
    source_batch_id: int,
) -> None:
    inv = (
        await session.scalars(
            select(GreenInventory).where(GreenInventory.variety_code == variety_code)
        )
    ).one()
    inv.quantity_kg = round(inv.quantity_kg - quantity_kg, 2)
    inv.last_updated_sim_time = sim_at
    session.add(
        GreenInventoryMovement(
            variety_code=variety_code,
            quantity_kg_delta=-quantity_kg,
            movement_type="consumption",
            source_batch_id=source_batch_id,
            sim_at=sim_at,
        )
    )


# =====================================================================
# In-progress batch advancement: telemetry stream + completion
# =====================================================================


async def advance_in_progress_batches(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng: random.Random,
    sim_now: datetime,
) -> None:
    in_progress = (
        await session.scalars(
            select(RoastingBatch).where(RoastingBatch.status == "in_progress")
        )
    ).all()
    if not in_progress:
        return

    total_sec = settings.roast_duration_sim_seconds
    interval = settings.telemetry_sample_interval_sim_seconds

    for batch in in_progress:
        completion_at = batch.sim_started_at + timedelta(seconds=total_sec)
        from_at = batch.last_telemetry_sim_at or batch.sim_started_at
        to_at = min(sim_now, completion_at)

        samples = samples_in_window(
            sim_started_at=batch.sim_started_at,
            from_sim_at=from_at,
            to_sim_at=to_at,
            interval_sec=interval,
            total_sec=total_sec,
            rng=rng,
        )
        for sim_at, s in samples:
            await publisher.publish_telemetry(
                RoasterTelemetry(
                    batch_id=batch.id,
                    batch_number=batch.batch_number,
                    sim_at=sim_at,
                    elapsed_seconds=s.elapsed_seconds,
                    drum_temp_celsius=s.drum_temp_celsius,
                    exhaust_temp_celsius=s.exhaust_temp_celsius,
                    fan_speed_pct=s.fan_speed_pct,
                    burner_pct=s.burner_pct,
                )
            )
        batch.last_telemetry_sim_at = to_at

        if sim_now >= completion_at:
            await _complete_batch(session, publisher, settings, rng, batch, completion_at)


async def _complete_batch(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng: random.Random,
    batch: RoastingBatch,
    sim_completed_at: datetime,
) -> None:
    weight_loss = max(0.05, min(0.30, rng.gauss(settings.weight_loss_mean, settings.weight_loss_stdev)))
    output_kg = round(batch.planned_input_kg * (1 - weight_loss), 2)
    cupping = max(0.0, min(100.0, rng.gauss(settings.cupping_mean, settings.cupping_stdev)))

    batch.sim_completed_at = sim_completed_at
    batch.output_kg = output_kg
    batch.weight_loss_pct = round(weight_loss, 4)
    batch.cupping_score = round(cupping, 1)

    sku = await session.get(RoastedSku, batch.sku_id)

    if cupping < settings.cupping_reject_threshold:
        batch.status = "rejected"
        batch.rejection_reason = rng.choice(REJECTION_REASONS)
        # Rejected lots do NOT enter saleable inventory.
    else:
        batch.status = "completed"
        # Credit roasted inventory
        roasted_inv = (
            await session.scalars(
                select(RoastedInventory).where(RoastedInventory.sku_id == batch.sku_id)
            )
        ).one()
        roasted_inv.quantity_kg = round(roasted_inv.quantity_kg + output_kg, 2)
        roasted_inv.last_updated_sim_time = sim_completed_at

    event = BatchCompleted(
        batch_id=batch.id,
        batch_number=batch.batch_number,
        sku_code=sku.code,
        brand=sku.brand,
        sim_started_at=batch.sim_started_at,
        sim_completed_at=sim_completed_at,
        input_kg=batch.planned_input_kg,
        output_kg=output_kg,
        weight_loss_pct=round(weight_loss, 4),
        cupping_score=round(cupping, 1),
        status=batch.status,  # type: ignore[arg-type]
        rejection_reason=batch.rejection_reason,
    )
    await publisher.publish_batch_completed(event)
