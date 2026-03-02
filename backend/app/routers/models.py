from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.dependencies import get_huggingface_service, get_ollama_service
from app.schemas.model import LocalModel, ModelPullRequest, ModelSearchResult
from app.services.huggingface_service import HuggingFaceService
from app.services.ollama_service import OllamaService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/local", response_model=list[LocalModel])
async def list_local_models(
    ollama: OllamaService = Depends(get_ollama_service),
):
    models = await ollama.list_models()
    return [
        LocalModel(
            name=m.get("name", ""),
            size=m.get("size", 0),
            parameter_size=m.get("details", {}).get("parameter_size"),
            quantization_level=m.get("details", {}).get("quantization_level"),
        )
        for m in models
    ]


@router.post("/pull")
async def pull_model(
    data: ModelPullRequest,
    ollama: OllamaService = Depends(get_ollama_service),
):
    async def event_generator():
        async for status in ollama.pull_model_stream(data.name):
            yield f"data: {json.dumps(status)}\n\n"

    return EventSourceResponse(event_generator(), media_type="text/event-stream")


@router.get("/search", response_model=list[ModelSearchResult])
async def search_models(
    q: str = Query(..., min_length=1),
    hf: HuggingFaceService = Depends(get_huggingface_service),
):
    return await hf.search_models(q)
