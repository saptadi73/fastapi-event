from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnnouncementWrite(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body: str = Field(min_length=2)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")
    published_at: datetime | None = None


class AnnouncementRead(AnnouncementWrite):
    id: UUID
    event_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CertificateWrite(BaseModel):
    event_id: UUID
    user_id: UUID
    certificate_number: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=2, max_length=255)
    download_url: str | None = None
    issued_at: datetime | None = None


class CertificateRead(BaseModel):
    id: UUID
    event_id: UUID
    user_id: UUID
    certificate_number: str
    title: str
    download_url: str | None
    issued_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
