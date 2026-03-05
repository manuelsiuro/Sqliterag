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
    default_model: str = "qwen3.5:9b"
    embedding_model: str = "nomic-embed-text"

    # Default generation parameters (Qwen3.5:9b-optimized)
    default_model_parameters: dict = {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "presence_penalty": 1.5,
        "num_predict": 2048,
    }

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

    # Dynamic tool injection (Phase 1.4)
    tool_injection_enabled: bool = True

    # Tool call validation (Phase 1.6)
    tool_validation_enabled: bool = True

    # Game memory hybrid search (Phase 2.3)
    memory_hybrid_search_enabled: bool = True
    memory_rrf_k: int = 60
    memory_weight_fts: float = 0.4
    memory_weight_vec: float = 0.6
    memory_search_top_k: int = 5
    memory_search_candidates_k: int = 20

    # Session summarization (Phase 2.6)
    session_summary_enabled: bool = True
    session_summary_max_tokens: int = 300

    # Stanford retrieval scoring (Phase 2.4)
    memory_stanford_scoring_enabled: bool = True
    memory_alpha_recency: float = 1.0
    memory_alpha_importance: float = 1.0
    memory_alpha_relevance: float = 1.0
    memory_recency_decay: float = 0.995

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
