from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttendanceRegistrant(BaseModel):
    registration_id: UUID
    event_id: UUID
    registration_number: str
    registration_status: str
    participant_id: UUID
    participant_name: str
    organization_name: str | None = None
    ticket_id: UUID | None = None
    ticket_number: str | None = None
    is_checked_in: bool = False
    check_in_id: UUID | None = None
    check_in_type: str | None = None
    check_in_at: datetime | None = None
    gate_name: str | None = None
    device_id: str | None = None
    check_in_by: UUID | None = None


class AttendanceSummary(BaseModel):
    event_id: UUID
    total_registered: int
    total_checked_in: int
    total_not_checked_in: int
    attendance_rate: float


class AttendanceReport(BaseModel):
    event_id: UUID
    summary: AttendanceSummary
    attendees: list[AttendanceRegistrant]

    model_config = ConfigDict(from_attributes=True)
