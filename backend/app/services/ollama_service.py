from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator

import httpx

from app.config import settings
from app.services.base import BaseEmbeddingService, BaseLLMService

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

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

    async def chat_stream(self, model: str, messages: list[dict], **kwargs) -> AsyncGenerator:
        payload = {"model": model, "messages": messages, "stream": True, **kwargs}
        in_think = False
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
                        # Strip leaked <think> blocks from streaming chunks
                        if "<think>" in content:
                            in_think = True
                        if in_think:
                            if "</think>" in content:
                                in_think = False
                                # Emit anything after the closing tag
                                after = content.split("</think>", 1)[1]
                                if after:
                                    yield after
                            continue
                        yield content
                    if chunk.get("done"):
                        # Yield the final chunk as a dict containing Ollama metrics
                        yield chunk
                        return

    async def chat(self, model: str, messages: list[dict], **kwargs) -> dict:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {})
            # Strip leaked <think> blocks from non-streaming response
            if message.get("content"):
                message["content"] = _THINK_BLOCK_RE.sub("", message["content"]).strip()
            # Attach Ollama metrics to the message dict for upstream consumers
            for key in ("total_duration", "load_duration", "prompt_eval_count",
                        "prompt_eval_duration", "eval_count", "eval_duration"):
                if key in data:
                    message[key] = data[key]
            return message

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
            full = embeddings[0]
            dim = settings.embedding_dimensions
            if dim and dim < len(full):
                return full[:dim]
            return full

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
