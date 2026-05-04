import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BlendRecipe, RoastedInventory, RoastedSku
from .seed_data import BLEND_RECIPES, ROASTED_SKUS

log = logging.getLogger(__name__)


async def seed_master_data(session: AsyncSession) -> None:
    existing_codes = set(
        (await session.scalars(select(RoastedSku.code))).all()
    )
    new_skus = [s for s in ROASTED_SKUS if s["code"] not in existing_codes]
    for s in new_skus:
        session.add(RoastedSku(code=s["code"], name=s["name"], brand=s["brand"]))
    if new_skus:
        await session.flush()
        log.info("seed.skus_added count=%d", len(new_skus))

    code_to_id = {
        code: id_ for code, id_ in (
            await session.execute(select(RoastedSku.code, RoastedSku.id))
        ).all()
    }

    # Recipes: only insert if no recipe rows exist for that SKU yet (idempotent
    # on first run, leaves human edits alone on subsequent runs).
    skus_with_recipes = set(
        (await session.scalars(select(BlendRecipe.sku_id))).all()
    )
    new_recipes = [
        r for r in BLEND_RECIPES
        if code_to_id[r["sku_code"]] not in skus_with_recipes
    ]
    for r in new_recipes:
        session.add(
            BlendRecipe(
                sku_id=code_to_id[r["sku_code"]],
                variety_code=r["variety_code"],
                percentage=r["percentage"],
            )
        )
    if new_recipes:
        log.info("seed.recipes_added count=%d", len(new_recipes))

    # Bootstrap empty roasted_inventory rows for every SKU.
    inv_existing = set(
        (await session.scalars(select(RoastedInventory.sku_id))).all()
    )
    now = datetime.now(timezone.utc)
    for code, id_ in code_to_id.items():
        if id_ not in inv_existing:
            session.add(
                RoastedInventory(sku_id=id_, quantity_kg=0.0, last_updated_sim_time=now)
            )

    await session.commit()
