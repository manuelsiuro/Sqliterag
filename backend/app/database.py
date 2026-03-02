from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import sqlite_vec
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def _load_sqlite_extensions(dbapi_connection, _connection_record):
    """Load sqlite-vec extension on every new connection.

    aiosqlite wraps the raw sqlite3.Connection, so we must unwrap it.
    macOS system Python may not have enable_load_extension compiled in —
    in that case we log a warning and continue without vector search.
    """
    # Unwrap: AsyncAdapt_aiosqlite_connection → aiosqlite.Connection → sqlite3.Connection
    raw_conn = getattr(dbapi_connection, "driver_connection", dbapi_connection)
    if hasattr(raw_conn, "_conn"):
        raw_conn = raw_conn._conn

    if not hasattr(raw_conn, "enable_load_extension"):
        logger.warning(
            "sqlite3.Connection lacks enable_load_extension — "
            "sqlite-vec will NOT be loaded. Use Homebrew or pyenv Python for full support."
        )
        return

    raw_conn.enable_load_extension(True)
    sqlite_vec.load(raw_conn)
    raw_conn.enable_load_extension(False)
    logger.info("sqlite-vec extension loaded")


async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create ORM tables and the vec0 virtual table."""
    from app.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
                    "USING vec0(embedding float[768])"
                )
            )
        except Exception:
            logger.warning(
                "Could not create vec_chunks table — "
                "vector search will be unavailable until sqlite-vec is loaded",
                exc_info=True,
            )
    logger.info("Database initialized")
