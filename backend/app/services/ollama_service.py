from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import httpx

from app.config import settings
from app.services.base import BaseEmbeddingService, BaseLLMService

logger = logging.getLogger(__name__)


class OllamaService(BaseLLMService, BaseEmbeddingService):
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.ollama_base_url
        self.embedding_model = settings.embedding_model

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return data.get("models", [])

    async def chat_stream(self, model: str, messages: list[dict], **kwargs) -> AsyncGenerator[str]:
        payload = {"model": model, "messages": messages, "stream": True, **kwargs}
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client,
            client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    import json

                    chunk = json.loads(line)
                    if content := chunk.get("message", {}).get("content", ""):
                        yield content
                    if chunk.get("done"):
                        return

    async def chat(self, model: str, messages: list[dict], **kwargs) -> dict:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json().get("message", {})

    async def show_model(self, name: str) -> dict:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            resp = await client.post(f"{self.base_url}/api/show", json={"name": name})
            resp.raise_for_status()
            return resp.json()

    async def generate_embedding(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.embedding_model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if not embeddings:
                raise ValueError("No embeddings returned from Ollama")
            return embeddings[0]

    async def pull_model_stream(self, name: str) -> AsyncGenerator[dict]:
        payload = {"name": name, "stream": True}
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client,
            client.stream("POST", f"{self.base_url}/api/pull", json=payload) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    import json

                    yield json.loads(line)
