from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: str
    chunk_index: int
    content: str


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    chunks_created: int
