import logging
import re

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

log = logging.getLogger(__name__)

_DSN_STRIP_DRIVER = re.compile(r"^postgresql\+asyncpg://")

# Idempotent column additions for the dirty-data layer. SQLAlchemy's
# create_all() only creates *new* tables; it doesn't add columns to existing
# ones. These ALTER statements keep older databases compatible without
# requiring a full reset.
_POST_CREATE_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS supplier_name_on_invoice VARCHAR(128)",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS invoice_currency VARCHAR(3)",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS invoice_amount DOUBLE PRECISION",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS fx_rate_recorded DOUBLE PRECISION",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS sim_actual_arrival TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS arrival_status VARCHAR(16)",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS quality_status VARCHAR(16)",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS quality_reason VARCHAR(128)",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS quantity_accepted_kg DOUBLE PRECISION",
    "CREATE INDEX IF NOT EXISTS ix_po_arrival_pending "
    "ON purchase_orders (sim_expected_arrival) WHERE arrival_status IS NULL",
)


async def ensure_database_exists(bootstrap_url: str, db_name: str) -> None:
    """`CREATE DATABASE` is not transactional, so use a raw asyncpg connection
    against the bootstrap (default) database to create our DB if missing."""
    raw_dsn = _DSN_STRIP_DRIVER.sub("postgresql://", bootstrap_url)
    conn = await asyncpg.connect(raw_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if exists:
            log.info("db.exists name=%s", db_name)
            return
        # Quote identifier defensively: db_name is operator-controlled config.
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", db_name):
            raise ValueError(f"refusing to create DB with unsafe name: {db_name!r}")
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        log.info("db.created name=%s", db_name)
    finally:
        await conn.close()


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("db.tables_ready")


async def apply_post_create_migrations(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for stmt in _POST_CREATE_MIGRATIONS:
            await conn.execute(text(stmt))
    log.info("db.post_create_migrations_applied count=%d", len(_POST_CREATE_MIGRATIONS))
