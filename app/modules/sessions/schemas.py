from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionBase(BaseModel):
    event_id: UUID
    workshop_track_id: UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=160)
    description: str | None = None
    session_type: str | None = None
    room_name: str | None = None
    start_at: datetime
    end_at: datetime
    capacity: int = Field(ge=1)
    status: str = "scheduled"


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    room_name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=1)
    status: str | None = None


class SessionRead(SessionBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)

