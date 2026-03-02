from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


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
    tool_calls: list | dict | None = None
    tool_name: str | None = None
    created_at: datetime

    @field_validator("tool_calls", mode="before")
    @classmethod
    def parse_tool_calls(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
