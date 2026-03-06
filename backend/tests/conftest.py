from __future__ import annotations

import sqlite3
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_session
from app.dependencies import get_chat_service, get_ollama_service, get_rag_service
from app.main import app
from app.models import Base
from app.services.chat_service import ChatService
from app.services.ollama_service import OllamaService
from app.services.rag_service import RAGService

TEST_DB_URL = "sqlite+aiosqlite://"

# Check if sqlite3 supports loading extensions (macOS system Python may not)
_HAS_LOAD_EXTENSION = hasattr(sqlite3.Connection, "enable_load_extension")


@pytest.fixture
async def engine():
    engine = create_async_engine(
        TEST_DB_URL, echo=False, connect_args={"check_same_thread": False}
    )

    if _HAS_LOAD_EXTENSION:
        import sqlite_vec

        @event.listens_for(engine.sync_engine, "connect")
        def _load_extensions(dbapi_connection, _connection_record):
            # Use the same unwrap logic as app/database.py
            raw_conn = getattr(dbapi_connection, "driver_connection", dbapi_connection)
            if hasattr(raw_conn, "_conn"):
                raw_conn = raw_conn._conn
            raw_conn.enable_load_extension(True)
            sqlite_vec.load(raw_conn)
            raw_conn.enable_load_extension(False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if _HAS_LOAD_EXTENSION:
            await conn.execute(
                text(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{settings.embedding_dimensions}])"
                )
            )
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def mock_ollama():
    service = MagicMock(spec=OllamaService)
    service.list_models = AsyncMock(
        return_value=[
            {
                "name": "llama3.2",
                "size": 2_000_000_000,
                "details": {"parameter_size": "3B", "quantization_level": "Q4_0"},
            }
        ]
    )
    service.generate_embedding = AsyncMock(return_value=[0.1] * settings.embedding_dimensions)
    return service


@pytest.fixture
def mock_rag(mock_ollama):
    return RAGService(embedding_service=mock_ollama)


@pytest.fixture
def mock_chat(mock_ollama, mock_rag):
    return ChatService(llm_service=mock_ollama, rag_service=mock_rag)


@pytest.fixture
async def client(engine, mock_ollama, mock_rag, mock_chat) -> AsyncGenerator[AsyncClient]:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_ollama_service] = lambda: mock_ollama
    app.dependency_overrides[get_rag_service] = lambda: mock_rag
    app.dependency_overrides[get_chat_service] = lambda: mock_chat

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
