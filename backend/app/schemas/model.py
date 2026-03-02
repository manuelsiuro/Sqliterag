from __future__ import annotations

from pydantic import BaseModel


class LocalModel(BaseModel):
    name: str
    size: int
    parameter_size: str | None = None
    quantization_level: str | None = None


class ModelPullRequest(BaseModel):
    name: str


class ModelSearchResult(BaseModel):
    id: str
    author: str | None = None
    downloads: int = 0
    likes: int = 0
    tags: list[str] = []
