from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CheckInBase(BaseModel):
    ticket_id: UUID
    event_id: UUID
    check_in_type: str = "qr"
    gate_name: str | None = None
    device_id: str | None = None
    status: str = "success"
    notes: str | None = None


class CheckInScanRequest(BaseModel):
    qr_token: str = Field(min_length=8)
    event_id: UUID
    gate_name: str | None = None
    device_id: str | None = None


class CheckInManualRequest(BaseModel):
    ticket_number: str = Field(min_length=5)
    event_id: UUID
    gate_name: str | None = None
    device_id: str | None = None


class CheckInRead(BaseModel):
    id: UUID
    ticket_id: UUID
    event_id: UUID
    session_id: UUID | None = None
    check_in_type: str
    check_in_at: datetime
    check_in_by: UUID | None = None
    gate_name: str | None = None
    device_id: str | None = None
    status: str
    notes: str | None = None

