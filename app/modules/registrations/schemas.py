from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegistrationBase(BaseModel):
    event_id: UUID
    participant_id: UUID
    ticket_type_id: UUID | None = None
    dietary_preference: str | None = None
    accessibility_requirements: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    consent_snapshot: str | None = None


class RegistrationCreate(RegistrationBase):
    pass


class RegistrationRead(BaseModel):
    id: UUID
    event_id: UUID
    participant_id: UUID
    registration_number: str
    status: str
    dietary_preference: str | None = None
    accessibility_requirements: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    confirmed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

