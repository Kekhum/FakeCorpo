import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Cafe, MenuItem
from .seed_data import CAFES, MENU_ITEMS

log = logging.getLogger(__name__)


async def seed_master_data(session: AsyncSession) -> None:
    existing_cafe_codes = set(
        (await session.scalars(select(Cafe.code))).all()
    )
    new_cafes = [c for c in CAFES if c["code"] not in existing_cafe_codes]
    for c in new_cafes:
        session.add(Cafe(**c))
    if new_cafes:
        log.info("seed.cafes_added count=%d", len(new_cafes))

    existing_item_codes = set(
        (await session.scalars(select(MenuItem.code))).all()
    )
    new_items = [m for m in MENU_ITEMS if m["code"] not in existing_item_codes]
    for m in new_items:
        session.add(MenuItem(**m))
    if new_items:
        log.info("seed.menu_items_added count=%d", len(new_items))

    await session.commit()
