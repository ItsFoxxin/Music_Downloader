from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTRACT_VERSION = "1.0"
IDENTITY_HEADER = "X-FoxDen-Identity"


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    label: str = Field(min_length=1, max_length=120)
    enabled: bool


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["healthy", "unhealthy"]
    summary: str = Field(min_length=1, max_length=200)


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=60)
    occurred_at: datetime
    path: str | None = Field(default=None, max_length=300)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str | None) -> str | None:
        if value is not None and (not value.startswith("/") or value.startswith("//") or ".." in value):
            raise ValueError("path must be a safe relative application path")
        return value


class ModuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    contract_version: Literal["1.0"]
    module_id: str = Field(min_length=1, max_length=40)
    module_name: str = Field(min_length=1, max_length=80)
    module_version: str = Field(min_length=1, max_length=40)
    health: Health
    capabilities: list[Capability] = Field(max_length=50)
    activity: list[Activity] = Field(max_length=20)


class ActivityFeed(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    contract_version: Literal["1.0"]
    module_id: str = Field(min_length=1, max_length=40)
    activity: list[Activity] = Field(max_length=20)
