from __future__ import annotations

from functools import lru_cache

from app.services.agent_orchestrator import AgentOrchestrator
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
    return AgentOrchestrator(agents=[RulesEngineAgent(), NarratorAgent()])


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(
        llm_service=get_ollama_service(),
        rag_service=get_rag_service(),
        tool_service=get_tool_service(),
        embedding_service=get_ollama_service(),
        orchestrator=get_orchestrator(),
    )


@lru_cache
def get_huggingface_service() -> HuggingFaceService:
    return HuggingFaceService()
