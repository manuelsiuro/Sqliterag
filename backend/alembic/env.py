from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import event
import sqlite_vec
import logging

from app.models import Base

logger = logging.getLogger('alembic.env')

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _load_sqlite_extensions(dbapi_connection, _connection_record):
    raw_conn = getattr(dbapi_connection, "driver_connection", dbapi_connection)
    if hasattr(raw_conn, "_conn"):
        raw_conn = raw_conn._conn

    if not hasattr(raw_conn, "enable_load_extension"):
        return

    try:
        raw_conn.enable_load_extension(True)
        sqlite_vec.load(raw_conn)
        raw_conn.enable_load_extension(False)
    except Exception as e:
        logger.warning(f"Could not load sqlite-vec in Alembic: {e}")

def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    
    # ensure vec is loaded on the synchronous connection underlying the async one
    _load_sqlite_extensions(connection.connection.dbapi_connection, None)
    
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
