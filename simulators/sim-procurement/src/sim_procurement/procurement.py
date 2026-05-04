import logging
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fakecorpo_shared.schemas.procurement import (
    PurchaseOrderCreated,
    PurchaseOrderLineCreated,
)

from .config import Settings
from .dirty import choose_invoice_money, choose_invoice_name
from .events import EventPublisher
from .models import CoffeeVariety, PurchaseOrder, PurchaseOrderLine, Supplier
from .seed_data import FX_RATES, SUPPLIER_NAME_VARIANTS

log = logging.getLogger(__name__)


def _po_number(sim_now: datetime, supplier_code: str, seq: int) -> str:
    return f"PO-{sim_now:%Y%m%d}-{supplier_code}-{seq:03d}"


async def _suppliers_with_varieties(
    session: AsyncSession,
) -> dict[Supplier, list[CoffeeVariety]]:
    rows = (
        await session.execute(
            select(Supplier, CoffeeVariety).join(
                CoffeeVariety, CoffeeVariety.supplier_id == Supplier.id
            )
        )
    ).all()
    by_supplier: dict[Supplier, list[CoffeeVariety]] = defaultdict(list)
    for supplier, variety in rows:
        by_supplier[supplier].append(variety)
    return by_supplier


async def run_procurement_round(
    session: AsyncSession,
    publisher: EventPublisher,
    settings: Settings,
    rng: random.Random,
    sim_now: datetime,
) -> list[PurchaseOrderCreated]:
    """Generate 1-3 POs against random suppliers, persist, publish events.

    Mutates session but does not commit — caller is responsible.
    """
    inventory = await _suppliers_with_varieties(session)
    if not inventory:
        log.warning("procurement.no_master_data — did seeding run?")
        return []

    n_pos = rng.randint(settings.min_pos_per_round, settings.max_pos_per_round)
    chosen_suppliers = rng.sample(
        list(inventory.keys()), k=min(n_pos, len(inventory))
    )

    real_now = datetime.now(timezone.utc)
    events: list[PurchaseOrderCreated] = []

    for seq, supplier in enumerate(chosen_suppliers, start=1):
        varieties = inventory[supplier]
        n_lines = rng.randint(
            settings.min_lines_per_po,
            min(settings.max_lines_per_po, len(varieties)),
        )
        chosen_varieties = rng.sample(varieties, k=n_lines)

        po_lines_input: list[tuple[CoffeeVariety, float, float, float]] = []
        contract_total = 0.0
        for variety in chosen_varieties:
            qty = float(rng.randint(settings.min_qty_kg, settings.max_qty_kg))
            unit_price = round(variety.base_price_usd_per_kg, 2)
            line_total = round(qty * unit_price, 2)
            contract_total += line_total
            po_lines_input.append((variety, qty, unit_price, line_total))
        contract_total = round(contract_total, 2)

        # Dirty layer: name on invoice, currency, FX.
        invoice_name = choose_invoice_name(
            canonical=supplier.name,
            variants=SUPPLIER_NAME_VARIANTS.get(supplier.code, []),
            rng=rng,
            p_variant=settings.p_invoice_name_variant,
        )
        money = choose_invoice_money(
            contract_amount=contract_total,
            contract_currency=supplier.currency,
            fx_rates=FX_RATES,
            rng=rng,
            p_invoice_in_eur=settings.p_invoice_in_eur,
            fx_jitter=settings.fx_jitter,
            p_missing_fx_rate=settings.p_missing_fx_rate,
        )

        shipping_days = rng.randint(
            settings.shipping_min_days, settings.shipping_max_days
        )
        po = PurchaseOrder(
            po_number=_po_number(sim_now, supplier.code, seq),
            supplier_id=supplier.id,
            sim_created_at=sim_now,
            sim_expected_arrival=sim_now + timedelta(days=shipping_days),
            real_created_at=real_now,
            currency=supplier.currency,
            total_amount=contract_total,
            supplier_name_on_invoice=invoice_name,
            invoice_currency=money.invoice_currency,
            invoice_amount=money.invoice_amount,
            fx_rate_recorded=money.fx_rate_recorded,
            status="placed",
        )
        session.add(po)
        await session.flush()  # to obtain po.id

        for variety, qty, unit_price, line_total in po_lines_input:
            session.add(
                PurchaseOrderLine(
                    po_id=po.id,
                    variety_id=variety.id,
                    quantity_kg=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        event = PurchaseOrderCreated(
            po_id=po.id,
            po_number=po.po_number,
            supplier_code=supplier.code,
            supplier_name=supplier.name,
            supplier_name_on_invoice=invoice_name,
            supplier_country=supplier.country,
            currency=po.currency,
            total_amount=po.total_amount,
            invoice_currency=money.invoice_currency,
            invoice_amount=money.invoice_amount,
            fx_rate_recorded=money.fx_rate_recorded,
            sim_created_at=po.sim_created_at,
            sim_expected_arrival=po.sim_expected_arrival,
            lines=[
                PurchaseOrderLineCreated(
                    variety_code=variety.code,
                    variety_name=variety.name,
                    quantity_kg=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                )
                for variety, qty, unit_price, line_total in po_lines_input
            ],
        )
        events.append(event)

    await session.flush()
    for event in events:
        await publisher.publish_po_created(event)

    log.info(
        "procurement.round_done sim_now=%s pos_created=%d total_value=%.2f",
        sim_now.isoformat(), len(events), sum(e.total_amount for e in events),
    )
    return events
