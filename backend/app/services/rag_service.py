from __future__ import annotations

import logging
import struct

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentChunk
from app.services.base import BaseEmbeddingService

logger = logging.getLogger(__name__)


def serialize_float32(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def extract_text(content: bytes, content_type: str, filename: str) -> str:
    if content_type == "application/pdf":
        import io

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    # Default: treat as text (txt, md, etc.)
    return content.decode("utf-8", errors="replace")


class RAGService:
    def __init__(self, embedding_service: BaseEmbeddingService):
        self.embedding_service = embedding_service
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    async def ingest_document(
        self,
        session: AsyncSession,
        document: Document,
        raw_content: bytes,
    ) -> int:
        text_content = extract_text(raw_content, document.content_type, document.filename)
        document.content = text_content

        chunks_text = self.splitter.split_text(text_content)
        if not chunks_text:
            logger.warning("No chunks generated for document %s", document.id)
            return 0

        chunk_objects = []
        for idx, chunk_text in enumerate(chunks_text):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                content=chunk_text,
            )
            session.add(chunk)
            chunk_objects.append((chunk, chunk_text))

        await session.flush()

        for chunk, chunk_text in chunk_objects:
            embedding = await self.embedding_service.generate_embedding(chunk_text)
            vec_bytes = serialize_float32(embedding)
            await session.execute(
                sql_text("INSERT INTO vec_chunks(rowid, embedding) VALUES (:rowid, :embedding)"),
                {"rowid": chunk.id, "embedding": vec_bytes},
            )

        logger.info("Ingested document %s: %d chunks", document.filename, len(chunk_objects))
        return len(chunk_objects)

    async def retrieve_context(
        self,
        session: AsyncSession,
        query: str,
        top_k: int | None = None,
    ) -> list[str]:
        k = top_k or settings.rag_top_k

        embedding = await self.embedding_service.generate_embedding(query)
        vec_bytes = serialize_float32(embedding)

        result = await session.execute(
            sql_text(
                "SELECT rowid, distance FROM vec_chunks "
                "WHERE embedding MATCH :query ORDER BY distance LIMIT :k"
            ),
            {"query": vec_bytes, "k": k},
        )
        rows = result.fetchall()

        if not rows:
            return []

        chunk_ids = [row[0] for row in rows]
        placeholders = ", ".join(str(cid) for cid in chunk_ids)
        chunk_result = await session.execute(
            sql_text(f"SELECT id, content FROM document_chunks WHERE id IN ({placeholders})")
        )
        chunk_map = {row[0]: row[1] for row in chunk_result.fetchall()}

        return [chunk_map[cid] for cid in chunk_ids if cid in chunk_map]

    async def delete_document_vectors(
        self,
        session: AsyncSession,
        document_id: str,
    ) -> None:
        chunk_result = await session.execute(
            sql_text("SELECT id FROM document_chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        chunk_ids = [row[0] for row in chunk_result.fetchall()]
        if chunk_ids:
            placeholders = ", ".join(str(cid) for cid in chunk_ids)
            await session.execute(
                sql_text(f"DELETE FROM vec_chunks WHERE rowid IN ({placeholders})")
            )
