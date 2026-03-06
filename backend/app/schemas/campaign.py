from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CampaignCreate(BaseModel):
    name: str
    description: str = ""


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class CampaignSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    session_number: int
    status: str
    world_name: str
    summary: str | None = None
    created_at: datetime


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    world_name: str
    description: str
    status: str
    session_count: int = 0
    created_at: datetime
    updated_at: datetime


class CampaignDetail(CampaignRead):
    sessions: list[CampaignSessionRead] = []
