from __future__ import annotations

import asyncio
import logging
from functools import partial

from huggingface_hub import HfApi

from app.schemas.model import ModelSearchResult

logger = logging.getLogger(__name__)


class HuggingFaceService:
    def __init__(self):
        self.api = HfApi()

    async def search_models(self, query: str, limit: int = 20) -> list[ModelSearchResult]:
        loop = asyncio.get_event_loop()
        models = await loop.run_in_executor(
            None,
            partial(
                self.api.list_models,
                search=query,
                filter="gguf",
                sort="downloads",
                direction=-1,
                limit=limit,
            ),
        )
        results = []
        for m in models:
            results.append(
                ModelSearchResult(
                    id=m.id,
                    author=m.author,
                    downloads=m.downloads or 0,
                    likes=m.likes or 0,
                    tags=list(m.tags) if m.tags else [],
                    last_modified=m.last_modified.isoformat() if m.last_modified else None,
                    pipeline_tag=getattr(m, "pipeline_tag", None),
                    url=f"https://huggingface.co/{m.id}",
                )
            )
        return results
