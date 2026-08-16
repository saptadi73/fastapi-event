import uuid
from datetime import date, datetime, time
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Visibility(str, PyEnum):
    ALL = "all"
    RECOMMENDED = "recommended"
    HIDDEN = "hidden"


class ConversationStatus(str, PyEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class MessageType(str, PyEnum):
    TEXT = "text"
    SYSTEM = "system"
    MEETING_REQUEST = "meeting_request"
    MEETING_ACCEPTED = "meeting_accepted"
    MEETING_DECLINED = "meeting_declined"
    MEETING_CONFIRMED = "meeting_confirmed"
    MEETING_RESCHEDULE = "meeting_reschedule"
    MEETING_CANCELLED = "meeting_cancelled"
    CONTACT_CARD = "contact_card"
    ATTACHMENT = "attachment"


class MeetingStatus(str, PyEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    SCHEDULING = "scheduling"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    RESCHEDULE_REQUESTED = "reschedule_requested"
    NO_SHOW = "no_show"


class BusinessMatchingProfile(Base):
    __tablename__ = "business_matching_profiles"
    __table_args__ = (
        UniqueConstraint("event_id", "participant_id", name="uq_business_profile_event_participant"),
        Index("ix_business_profile_event_available", "event_id", "available_for_matching"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    registration_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), unique=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    organization_name: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(3))
    organization_type: Mapped[str | None] = mapped_column(String(80))
    position_title: Mapped[str | None] = mapped_column(String(160))
    short_description: Mapped[str | None] = mapped_column(Text)
    target_market: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    preferred_regions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_interests: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_sectors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    technology_interests: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    partnership_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_offerings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    business_needs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    representative: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(60))
    products: Mapped[str | None] = mapped_column(Text)
    services: Mapped[str | None] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(100))
    production_capacity: Mapped[str | None] = mapped_column(Text)
    certificates: Mapped[str | None] = mapped_column(Text)
    markets_served: Mapped[str | None] = mapped_column(Text)
    preferred_slot_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    estimated_deal_investment_value: Mapped[str | None] = mapped_column(String(255))
    additional_notes: Mapped[str | None] = mapped_column(Text)
    profile_sharing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile_sharing_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_for_matching: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility, native_enum=False), default=Visibility.ALL, nullable=False)
    allow_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_meeting_requests: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ParticipantBlock(Base):
    __tablename__ = "participant_blocks"
    __table_args__ = (UniqueConstraint("event_id", "blocker_id", "blocked_id", name="uq_participant_block"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    blocker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    blocked_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ParticipantReport(Base):
    __tablename__ = "participant_reports"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    reported_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_event_last_message", "event_id", "last_message_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus, native_enum=False), default=ConversationStatus.ACTIVE, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (UniqueConstraint("conversation_id", "participant_id", name="uq_conversation_participant"), Index("ix_cp_participant_conversation", "participant_id", "conversation_id"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType, native_enum=False), default=MessageType.TEXT, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchingSession(Base):
    __tablename__ = "matching_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class MeetingSlot(Base):
    __tablename__ = "meeting_slots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    matching_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matching_sessions.id", ondelete="CASCADE"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="available", nullable=False)


class MeetingVenue(Base):
    __tablename__ = "meeting_venues"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_description: Mapped[str | None] = mapped_column(Text)


class MeetingResource(Base):
    __tablename__ = "meeting_resources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meeting_venues.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (Index("ix_meetings_event_status", "event_id", "status"), Index("ix_meetings_resource_slot", "venue_resource_id", "confirmed_slot_id", unique=True),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id"))
    requester_participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    recipient_participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus, native_enum=False), default=MeetingStatus.REQUESTED, nullable=False)
    confirmed_slot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meeting_slots.id"))
    venue_resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meeting_resources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MeetingSlotProposal(Base):
    __tablename__ = "meeting_slot_proposals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meeting_slots.id"), nullable=False)
    proposed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "business_matching_audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSON)
    new_values: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
