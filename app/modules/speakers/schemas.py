from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SpeakerBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    professional_title: str | None = None
    organization_name: str | None = None
    country_code: str | None = None
    biography: str | None = None
    profile_photo_url: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    expertise_tags: list[str] | None = None
    session_title: str | None = None
    is_featured: bool = False
    status: str = "draft"


class SpeakerCreate(SpeakerBase):
    user_id: UUID | None = None


class SpeakerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    professional_title: str | None = None
    organization_name: str | None = None
    biography: str | None = None
    profile_photo_url: str | None = None
    session_title: str | None = None
    status: str | None = None
    is_featured: bool | None = None


class SpeakerRead(SpeakerBase):
    id: UUID
    user_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
