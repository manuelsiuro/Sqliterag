from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    message: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
