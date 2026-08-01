from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParticipantProfileBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    organization_name: str | None = Field(default=None, max_length=255)
    biography: str | None = None
    profile_photo_url: str | None = None


class ParticipantProfileCreate(ParticipantProfileBase):
    pass


class ParticipantProfileUpdate(ParticipantProfileBase):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    organization_name: str | None = Field(default=None, max_length=255)
    biography: str | None = None
    profile_photo_url: str | None = None


class ParticipantProfileRead(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    organization_name: str | None = None
    biography: str | None = None
    profile_photo_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
