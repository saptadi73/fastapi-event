from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventBase(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    slug: str = Field(min_length=3, max_length=120)
    description: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    timezone: str = "Asia/Jakarta"
    start_at: datetime
    end_at: datetime
    capacity: int = Field(ge=1)


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: str | None = None
    slug: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    timezone: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=1)
    status: str | None = None


class EventRead(EventBase):
    id: UUID
    status: str

    model_config = ConfigDict(from_attributes=True)
