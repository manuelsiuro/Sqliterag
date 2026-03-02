from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_rag_service
from app.exceptions import NotFoundError
from app.models.document import Document
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services.rag_service import RAGService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    rag_service: RAGService = Depends(get_rag_service),
):
    raw_content = await file.read()

    doc = Document(
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(raw_content),
        content="",  # Will be set during ingestion
    )
    session.add(doc)
    await session.flush()

    chunks_created = await rag_service.ingest_document(session, doc, raw_content)
    await session.commit()
    await session.refresh(doc)

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(doc),
        chunks_created=chunks_created,
    )


@router.get("", response_model=list[DocumentRead])
async def list_documents(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    rag_service: RAGService = Depends(get_rag_service),
):
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document", document_id)

    await rag_service.delete_document_vectors(session, document_id)
    await session.delete(doc)
    await session.commit()
