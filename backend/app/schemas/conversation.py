from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model: str = "llama3.2"


class ConversationUpdate(BaseModel):
    title: str | None = None
    model: str | None = None


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime


class ConversationWithMessages(ConversationRead):
    messages: list[MessageRead] = []


from app.schemas.message import MessageRead  # noqa: E402, F811
