from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TemplateWrite(BaseModel):
    is_enabled: bool = True
    subject_template: str = Field(min_length=1, max_length=255)
    body_template: str = Field(min_length=1, max_length=20000)

    @field_validator("subject_template", "body_template")
    @classmethod
    def reject_header_injection(cls, value: str) -> str:
        if "\r" in value:
            raise ValueError("Carriage return tidak diizinkan")
        return value.strip()

    @field_validator("subject_template")
    @classmethod
    def subject_must_be_single_line(cls, value: str) -> str:
        if "\n" in value:
            raise ValueError("Subjek email harus satu baris")
        return value


class TemplateRead(TemplateWrite):
    id: UUID
    event_id: UUID
    trigger: str
    available_variables: list[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PreviewRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


class TestSendRequest(PreviewRequest):
    recipient: str = Field(min_length=6, max_length=255)

    @field_validator("recipient")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Email tidak valid")
        return value


class LogRead(BaseModel):
    id: UUID
    trigger: str
    recipient: str
    subject: str
    entity_type: str | None
    entity_id: UUID | None
    status: str
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
