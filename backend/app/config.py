from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # Database
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'sqliterag.db'}"

    # Models
    default_model: str = "llama3.2"
    embedding_model: str = "nomic-embed-text"

    # RAG
    chunk_size: int = 500
    chunk_overlap: int = 50
    rag_top_k: int = 5

    # Context window
    default_num_ctx: int = 8192

    # Conversation history summarization (Phase 1.2)
    history_summary_enabled: bool = True
    history_summarization_threshold: float = 0.7
    history_preserve_recent: int = 10
    history_summary_max_tokens: int = 200

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "app": {"level": "DEBUG", "propagate": True},
        "uvicorn": {"level": "INFO", "propagate": False, "handlers": ["console"]},
        "sqlalchemy.engine": {"level": "WARNING", "propagate": False, "handlers": ["console"]},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
