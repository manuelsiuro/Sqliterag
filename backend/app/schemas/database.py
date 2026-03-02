from __future__ import annotations

from pydantic import BaseModel


class TableInfo(BaseModel):
    name: str
    row_count: int


class DatabaseInfo(BaseModel):
    file_path: str
    file_size_bytes: int
    sqlite_version: str
    table_count: int
    tables: list[TableInfo]
