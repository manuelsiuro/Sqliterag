from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.dependencies import get_huggingface_service, get_ollama_service
from app.schemas.model import LocalModel, ModelDetail, ModelPullRequest, ModelSearchResult
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


@router.get("/{model_name:path}/details", response_model=ModelDetail)
async def get_model_details(
    model_name: str,
    ollama: OllamaService = Depends(get_ollama_service),
):
    data = await ollama.show_model(model_name)
    details = data.get("details", {})
    model_info = data.get("model_info", {})

    # Search model_info keys for context_length
    context_length = None
    for key, value in model_info.items():
        if "context_length" in key and isinstance(value, int):
            context_length = value
            break

    return ModelDetail(
        name=model_name,
        family=details.get("family"),
        families=details.get("families", []),
        parameter_size=details.get("parameter_size"),
        quantization_level=details.get("quantization_level"),
        context_length=context_length,
        format=details.get("format"),
        parent_model=details.get("parent_model"),
    )


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
