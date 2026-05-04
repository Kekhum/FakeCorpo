import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CoffeeVariety, Supplier
from .seed_data import SUPPLIERS, VARIETIES

log = logging.getLogger(__name__)


async def seed_master_data(session: AsyncSession) -> None:
    """Idempotent: only inserts rows that don't already exist (matched by `code`)."""

    existing_supplier_codes = set(
        (await session.scalars(select(Supplier.code))).all()
    )
    new_suppliers = [s for s in SUPPLIERS if s["code"] not in existing_supplier_codes]
    now = datetime.now(timezone.utc)
    for s in new_suppliers:
        session.add(
            Supplier(
                code=s["code"],
                name=s["name"],
                country=s["country"],
                currency=s["currency"],
                payment_terms_days=s["payment_terms_days"],
                quality_rating=s["quality_rating"],
                created_at=now,
            )
        )
    if new_suppliers:
        await session.flush()
        log.info("seed.suppliers_added count=%d", len(new_suppliers))

    code_to_supplier_id = {
        code: id_ for code, id_ in (
            await session.execute(select(Supplier.code, Supplier.id))
        ).all()
    }

    existing_variety_codes = set(
        (await session.scalars(select(CoffeeVariety.code))).all()
    )
    new_varieties = [v for v in VARIETIES if v["code"] not in existing_variety_codes]
    for v in new_varieties:
        session.add(
            CoffeeVariety(
                code=v["code"],
                name=v["name"],
                supplier_id=code_to_supplier_id[v["supplier_code"]],
                origin_country=v["origin_country"],
                region=v["region"],
                variety=v["variety"],
                processing=v["processing"],
                grade=v["grade"],
                base_price_usd_per_kg=v["base_price_usd_per_kg"],
            )
        )
    if new_varieties:
        log.info("seed.varieties_added count=%d", len(new_varieties))

    await session.commit()
