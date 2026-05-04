import logging
import re

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

log = logging.getLogger(__name__)

_DSN_STRIP_DRIVER = re.compile(r"^postgresql\+asyncpg://")


async def ensure_database_exists(bootstrap_url: str, db_name: str) -> None:
    raw_dsn = _DSN_STRIP_DRIVER.sub("postgresql://", bootstrap_url)
    conn = await asyncpg.connect(raw_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if exists:
            log.info("db.exists name=%s", db_name)
            return
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
