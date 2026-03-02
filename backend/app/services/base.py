from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class BaseLLMService(ABC):
    @abstractmethod
    async def list_models(self) -> list[dict]: ...

    @abstractmethod
    async def chat_stream(
        self, model: str, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str]: ...

    @abstractmethod
    async def chat(self, model: str, messages: list[dict], **kwargs) -> dict: ...

    @abstractmethod
    async def pull_model_stream(self, name: str) -> AsyncGenerator[dict]: ...


class BaseEmbeddingService(ABC):
    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]: ...
