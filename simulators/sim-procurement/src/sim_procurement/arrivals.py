import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fakecorpo_shared.schemas.procurement import (
    PurchaseOrderArrived,
    PurchaseOrderArrivedLine,
)

from .config import Settings
from .dirty import decide_arrival, decide_quality
from .events import EventPublisher
from .models import CoffeeVariety, PurchaseOrder, PurchaseOrderLine, Supplier
from .seed_data import QUALITY_PARTIAL_REASONS, QUALITY_REJECTED_REASONS

log = logging.getLogger(__name__)


async def run_arrivals_scan(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng: random.Random,
    sim_now: datetime,
) -> list[PurchaseOrderArrived]:
    """Settle every PO whose `sim_expected_arrival` is on or before `sim_now`
    and which hasn't been settled yet. One outcome per PO."""

    due = (
        await session.scalars(
            select(PurchaseOrder)
            .where(PurchaseOrder.arrival_status.is_(None))
            .where(PurchaseOrder.sim_expected_arrival <= sim_now)
            .order_by(PurchaseOrder.sim_expected_arrival)
        )
    ).all()

    if not due:
        return []

    events: list[PurchaseOrderArrived] = []

    for po in due:
        # Per-line ordered quantities, joined with variety code so that
        # the event downstream consumers receive is self-contained.
        line_rows = (
            await session.execute(
                select(PurchaseOrderLine.quantity_kg, CoffeeVariety.code)
                .join(CoffeeVariety, CoffeeVariety.id == PurchaseOrderLine.variety_id)
                .where(PurchaseOrderLine.po_id == po.id)
            )
        ).all()
        qty_ordered = sum(qty for qty, _ in line_rows)

        arrival = decide_arrival(rng)

        if arrival.status == "lost":
            po.arrival_status = "lost"
            po.sim_actual_arrival = None
            po.quality_status = None
            po.quality_reason = None
            po.quantity_accepted_kg = 0.0
            po.status = "lost"
            accepted_fraction = 0.0
            event_lines = [
                PurchaseOrderArrivedLine(
                    variety_code=code,
                    quantity_ordered_kg=qty,
                    quantity_accepted_kg=0.0,
                )
                for qty, code in line_rows
            ]
            event = PurchaseOrderArrived(
                po_id=po.id,
                po_number=po.po_number,
                supplier_code=(await _supplier_code(session, po.supplier_id)),
                sim_expected_arrival=po.sim_expected_arrival,
                sim_actual_arrival=None,
                arrival_status="lost",
                delay_days=0,
                quality_status=None,
                quality_reason=None,
                quantity_ordered_kg=qty_ordered,
                quantity_accepted_kg=0.0,
                lines=event_lines,
            )
        else:
            actual = po.sim_expected_arrival + timedelta(days=arrival.delay_days)
            quality = decide_quality(
                rng, QUALITY_PARTIAL_REASONS, QUALITY_REJECTED_REASONS
            )
            accepted_fraction = quality.accepted_fraction
            accepted = round(qty_ordered * accepted_fraction, 2)

            po.arrival_status = arrival.status
            po.sim_actual_arrival = actual
            po.quality_status = quality.status
            po.quality_reason = quality.reason
            po.quantity_accepted_kg = accepted
            po.status = "arrived"
            event_lines = [
                PurchaseOrderArrivedLine(
                    variety_code=code,
                    quantity_ordered_kg=qty,
                    quantity_accepted_kg=round(qty * accepted_fraction, 2),
                )
                for qty, code in line_rows
            ]
            event = PurchaseOrderArrived(
                po_id=po.id,
                po_number=po.po_number,
                supplier_code=(await _supplier_code(session, po.supplier_id)),
                sim_expected_arrival=po.sim_expected_arrival,
                sim_actual_arrival=actual,
                arrival_status=arrival.status,
                delay_days=arrival.delay_days,
                quality_status=quality.status,
                quality_reason=quality.reason,
                quantity_ordered_kg=qty_ordered,
                quantity_accepted_kg=accepted,
                lines=event_lines,
            )
        events.append(event)

    await session.flush()
    for event in events:
        await publisher.publish_po_arrived(event)

    counts: dict[str, int] = {}
    for e in events:
        counts[e.arrival_status] = counts.get(e.arrival_status, 0) + 1
    log.info(
        "arrivals.scan_done sim_now=%s settled=%d breakdown=%s",
        sim_now.isoformat(), len(events), counts,
    )
    return events


async def _supplier_code(session: AsyncSession, supplier_id: int) -> str:
    code = await session.scalar(
        select(Supplier.code).where(Supplier.id == supplier_id)
    )
    return code or "UNKNOWN"
