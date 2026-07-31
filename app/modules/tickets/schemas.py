from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TicketRead(BaseModel):
    id: UUID
    registration_id: UUID
    ticket_number: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class TicketIssueRequest(BaseModel):
    registration_id: UUID
