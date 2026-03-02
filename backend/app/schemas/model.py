from __future__ import annotations

from pydantic import BaseModel


class LocalModel(BaseModel):
    name: str
    size: int
    parameter_size: str | None = None
    quantization_level: str | None = None


class ModelPullRequest(BaseModel):
    name: str


class ModelDetail(BaseModel):
    name: str
    family: str | None = None
    families: list[str] = []
    parameter_size: str | None = None
    quantization_level: str | None = None
    context_length: int | None = None
    format: str | None = None
    parent_model: str | None = None


class ModelSearchResult(BaseModel):
    id: str
    author: str | None = None
    downloads: int = 0
    likes: int = 0
    tags: list[str] = []
    last_modified: str | None = None
    pipeline_tag: str | None = None
    url: str | None = None
