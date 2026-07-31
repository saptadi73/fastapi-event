from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkshopTrackBase(BaseModel):
    event_id: UUID
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    capacity: int = Field(ge=0)
    order_index: int = Field(default=0, ge=0)


class WorkshopTrackCreate(WorkshopTrackBase):
    pass


class WorkshopTrackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    capacity: int | None = Field(default=None, ge=0)
    order_index: int | None = Field(default=None, ge=0)


class WorkshopTrackRead(WorkshopTrackBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

