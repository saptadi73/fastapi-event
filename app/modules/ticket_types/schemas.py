from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TicketTypeBase(BaseModel):
    event_id: UUID
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    price: float = Field(ge=0)
    currency: str = "IDR"
    capacity: int = Field(ge=0)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
    is_active: bool = True


class TicketTypeCreate(TicketTypeBase):
    pass


class TicketTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    capacity: int | None = Field(default=None, ge=0)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
    is_active: bool | None = None


class TicketTypeRead(TicketTypeBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)

