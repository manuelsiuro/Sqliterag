from __future__ import annotations

from functools import lru_cache

from app.services.agent_orchestrator import AgentOrchestrator
from app.services.archivist_agent import ArchivistAgent
from app.services.frontend_bridge import FrontendBridge
from app.services.narrator_agent import NarratorAgent
from app.services.rules_engine_agent import RulesEngineAgent
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.ollama_service import OllamaService
from app.services.rag_service import RAGService
from app.services.tool_service import ToolService


@lru_cache
def get_ollama_service() -> OllamaService:
    return OllamaService()


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService(embedding_service=get_ollama_service())


@lru_cache
def get_tool_service() -> ToolService:
    return ToolService()


@lru_cache
def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(agents=[
        RulesEngineAgent(),   # COMBAT only
        NarratorAgent(),      # All phases (user-facing)
        ArchivistAgent(),     # All phases (silent, last)
    ])


@lru_cache
def get_frontend_bridge() -> FrontendBridge:
    from app.config import settings
    return FrontendBridge(default_timeout=settings.frontend_bridge_timeout)


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(
        llm_service=get_ollama_service(),
        rag_service=get_rag_service(),
        tool_service=get_tool_service(),
        embedding_service=get_ollama_service(),
        orchestrator=get_orchestrator(),
        frontend_bridge=get_frontend_bridge(),
    )


@lru_cache
def get_huggingface_service() -> HuggingFaceService:
    return HuggingFaceService()
