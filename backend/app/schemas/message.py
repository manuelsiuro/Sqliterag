from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelParameters(BaseModel):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    num_ctx: int | None = None
    repeat_penalty: float | None = None
    seed: int | None = None


class MessageCreate(BaseModel):
    message: str
    parameters: ModelParameters | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
