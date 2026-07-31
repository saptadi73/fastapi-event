import uuid
from enum import Enum as PyEnum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RegistrationStatus(str, PyEnum):
    DRAFT = "draft"
    WAITING_PAYMENT = "awaiting_payment"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"
    EXPIRED = "expired"


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("event_id", "participant_id", name="uq_registration_event_participant"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    ticket_type_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    registration_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[RegistrationStatus] = mapped_column(Enum(RegistrationStatus, native_enum=False), default=RegistrationStatus.DRAFT)
    dietary_preference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    accessibility_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    consent_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
