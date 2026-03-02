from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_session
from app.schemas.database import DatabaseInfo, TableInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/database", tags=["database"])


def _db_path() -> Path:
    """Extract the file path from the database URL."""
    url = settings.database_url
    # Strip 'sqlite+aiosqlite:///' prefix
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        return Path(url[len(prefix):])
    # Fallback: strip 'sqlite:///'
    return Path(url.split("///", 1)[1])


@router.get("/info", response_model=DatabaseInfo)
async def database_info(session: AsyncSession = Depends(get_session)):
    """Return database metadata: file size, SQLite version, tables and row counts."""
    db_path = _db_path()
    file_size = db_path.stat().st_size if db_path.exists() else 0

    version_row = await session.execute(text("SELECT sqlite_version()"))
    sqlite_version = version_row.scalar_one()

    tables_rows = await session.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    )
    table_names = [row[0] for row in tables_rows]

    tables: list[TableInfo] = []
    for name in table_names:
        count_row = await session.execute(text(f"SELECT COUNT(*) FROM \"{name}\""))  # noqa: S608
        tables.append(TableInfo(name=name, row_count=count_row.scalar_one()))

    return DatabaseInfo(
        file_path=str(db_path),
        file_size_bytes=file_size,
        sqlite_version=sqlite_version,
        table_count=len(tables),
        tables=tables,
    )


@router.post("/vacuum")
async def vacuum_database():
    """Run VACUUM to reclaim unused space. Must run outside a transaction."""
    db_path = _db_path()

    # VACUUM cannot run inside a transaction, so use raw connection
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("VACUUM"))

    new_size = db_path.stat().st_size if db_path.exists() else 0
    return {"status": "ok", "file_size_bytes": new_size}


@router.post("/clear-conversations")
async def clear_conversations(session: AsyncSession = Depends(get_session)):
    """Delete all messages and conversations."""
    msg_result = await session.execute(text("DELETE FROM messages"))
    conv_result = await session.execute(text("DELETE FROM conversations"))
    await session.commit()
    deleted = (msg_result.rowcount or 0) + (conv_result.rowcount or 0)
    return {"deleted": deleted}


@router.post("/clear-documents")
async def clear_documents(session: AsyncSession = Depends(get_session)):
    """Delete all vector chunks, document chunks, and documents."""
    deleted = 0
    # vec_chunks may not exist if sqlite-vec isn't loaded
    try:
        vec_result = await session.execute(text("DELETE FROM vec_chunks"))
        deleted += vec_result.rowcount or 0
    except Exception:
        logger.warning("Could not clear vec_chunks (table may not exist)")
    chunk_result = await session.execute(text("DELETE FROM document_chunks"))
    doc_result = await session.execute(text("DELETE FROM documents"))
    await session.commit()
    deleted += (chunk_result.rowcount or 0) + (doc_result.rowcount or 0)
    return {"deleted": deleted}


@router.get("/export")
async def export_database():
    """Download the SQLite database file."""
    db_path = _db_path()
    return FileResponse(
        path=str(db_path),
        filename=db_path.name,
        media_type="application/x-sqlite3",
    )
