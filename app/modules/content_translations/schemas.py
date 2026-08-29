from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TranslationWrite(BaseModel):
    fields: dict[str, Any] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def fields_must_have_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        if any(item is None or (isinstance(item, str) and not item.strip()) for item in value.values()):
            raise ValueError("Translation fields cannot contain null or blank values")
        return value


class TranslationRead(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    locale: Literal["en", "zh-CN"]
    fields: dict[str, Any]
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
