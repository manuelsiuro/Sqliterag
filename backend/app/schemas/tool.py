from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ToolParameterProperty(BaseModel):
    type: str
    description: str = ""
    enum: list[str] | None = None


class ToolParametersSchema(BaseModel):
    type: str = "object"
    required: list[str] = []
    properties: dict[str, ToolParameterProperty] = {}


class ToolCreate(BaseModel):
    name: str
    description: str
    parameters_schema: ToolParametersSchema
    execution_type: str = "mock"
    execution_config: dict = {}


class ToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parameters_schema: ToolParametersSchema | None = None
    execution_type: str | None = None
    execution_config: dict | None = None
    is_enabled: bool | None = None


class ToolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    parameters_schema: ToolParametersSchema | dict
    execution_type: str
    execution_config: dict
    is_enabled: bool
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("parameters_schema", mode="before")
    @classmethod
    def parse_parameters_schema(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("execution_config", mode="before")
    @classmethod
    def parse_execution_config(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class ConversationToolToggle(BaseModel):
    tool_ids: list[str]
