from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommitteeMemberBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    role_title: str = Field(min_length=2, max_length=255)
    committee_group: str | None = Field(default=None, max_length=160)
    organization_name: str | None = Field(default=None, max_length=255)
    biography: str | None = Field(default=None, max_length=20_000)
    profile_photo_url: str | None = None
    display_order: int = Field(default=0, ge=0)
    is_featured: bool = False
    status: Literal["draft", "published", "archived"] = "draft"


class CommitteeMemberCreate(CommitteeMemberBase):
    event_id: UUID


class CommitteeMemberUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role_title: str | None = Field(default=None, min_length=2, max_length=255)
    committee_group: str | None = Field(default=None, max_length=160)
    organization_name: str | None = Field(default=None, max_length=255)
    biography: str | None = Field(default=None, max_length=20_000)
    profile_photo_url: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_featured: bool | None = None
    status: Literal["draft", "published", "archived"] | None = None


class CommitteeMemberRead(CommitteeMemberBase):
    id: UUID
    event_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
