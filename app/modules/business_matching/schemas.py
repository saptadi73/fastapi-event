from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .models import MeetingStatus, MessageType, Visibility


class ProfileWrite(BaseModel):
    organization_name: str | None = Field(None, max_length=255)
    country_code: str | None = Field(None, min_length=2, max_length=3)
    organization_type: str | None = Field(None, max_length=80)
    position_title: str | None = Field(None, max_length=160)
    short_description: str | None = Field(None, max_length=2000)
    target_market: list[str] = []
    preferred_regions: list[str] = []
    business_interests: list[str] = []
    business_sectors: list[str] = []
    technology_interests: list[str] = []
    partnership_types: list[str] = []
    business_offerings: list[str] = []
    business_needs: list[str] = []
    available_for_matching: bool = True
    visibility: Visibility = Visibility.ALL
    allow_messages: bool = True
    allow_meeting_requests: bool = True

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value):
        return value.upper() if value else value


class ProfileRead(ProfileWrite):
    id: UUID
    event_id: UUID
    participant_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DiscoveryRead(ProfileRead):
    full_name: str
    profile_photo_url: str | None = None
    match_score: int | None = None
    match_reasons: list[str] = []


class ConversationCreate(BaseModel):
    participant_id: UUID
    initial_message: str | None = Field(None, min_length=1, max_length=5000)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    reply_to_message_id: UUID | None = None


class MessageUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_participant_id: UUID
    message_type: MessageType
    body: str
    meeting_id: UUID | None
    reply_to_message_id: UUID | None
    created_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ConversationRead(BaseModel):
    id: UUID
    event_id: UUID
    status: str
    last_message_at: datetime | None = None
    unread_count: int = 0
    other_participant_id: UUID
    other_participant_name: str
    other_participant_photo_url: str | None = None
    last_message: MessageRead | None = None


class MeetingCreate(BaseModel):
    recipient_participant_id: UUID
    conversation_id: UUID | None = None
    purpose: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=255)
    description: str | None = Field(None, max_length=3000)
    proposed_slot_ids: list[UUID] = []


class MeetingConfirm(BaseModel):
    slot_id: UUID
    resource_id: UUID


class ParticipantModeration(BaseModel):
    participant_id: UUID
    reason: str | None = Field(None, max_length=120)
    details: str | None = Field(None, max_length=2000)


class MeetingRead(BaseModel):
    id: UUID
    event_id: UUID
    conversation_id: UUID | None
    requester_participant_id: UUID
    recipient_participant_id: UUID
    purpose: str
    topic: str
    description: str | None
    status: MeetingStatus
    confirmed_slot_id: UUID | None
    venue_resource_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
