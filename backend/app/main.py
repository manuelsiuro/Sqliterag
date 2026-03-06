from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.exceptions import AppError, app_error_handler, generic_error_handler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initializing database")
    await init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="sqliteRAG",
    description="Local-first chat with Ollama + RAG using SQLite",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Import and mount routers
from app.routers import campaigns, chat, conversations, database, documents, models, settings, tools  # noqa: E402

app.include_router(conversations.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(database.router, prefix="/api")
app.include_router(tools.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
