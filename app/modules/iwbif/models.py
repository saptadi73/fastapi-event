import uuid
from datetime import date, datetime, time
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DelegatePackage(Base):
    __tablename__ = "delegate_packages"
    __table_args__ = (UniqueConstraint("event_id", "code", name="uq_delegate_package_event_code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    package_type: Mapped[str] = mapped_column(String(20), default="main", nullable=False)
    selection_mode: Mapped[str] = mapped_column(String(20), default="required_one", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    payment_amount_idr: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DelegatePackageRate(Base):
    __tablename__ = "delegate_package_rates"
    __table_args__ = (UniqueConstraint("delegate_package_id", "occupancy_type", name="uq_delegate_package_occupancy"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delegate_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delegate_packages.id", ondelete="CASCADE"), nullable=False)
    occupancy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    payment_amount_idr: Mapped[float | None] = mapped_column(Numeric(18, 2))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DelegatePackageFacility(Base):
    __tablename__ = "delegate_package_facilities"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delegate_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delegate_packages.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(40))
    pricing_mode: Mapped[str] = mapped_column(String(30), default="included", nullable=False)
    sharing_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    single_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EventActivity(Base):
    __tablename__ = "event_activities"
    __table_args__ = (UniqueConstraint("event_id", "name", name="uq_event_activity_name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BusinessMatchingSlot(Base):
    __tablename__ = "business_matching_slots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("participant_id", name="uq_company_participant"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DelegateRegistrationDetail(Base):
    __tablename__ = "delegate_registration_details"
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    delegate_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delegate_packages.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    company_organization: Mapped[str] = mapped_column(String(255), nullable=False)
    nationality: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(30), nullable=False)
    business_sector: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    office_phone: Mapped[str | None] = mapped_column(String(60))
    company_website: Mapped[str | None] = mapped_column(Text)
    linkedin: Mapped[str | None] = mapped_column(Text)
    company_address: Mapped[str] = mapped_column(Text, nullable=False)
    participation_categories: Mapped[list] = mapped_column(JSON, nullable=False)
    presentation_topic: Mapped[str | None] = mapped_column(Text)
    products_interested: Mapped[str | None] = mapped_column(Text)
    investment_interest: Mapped[str | None] = mapped_column(Text)
    room_preference: Mapped[str] = mapped_column(String(80), nullable=False)
    preferred_roommate: Mapped[str | None] = mapped_column(String(255))
    arrival_date: Mapped[date] = mapped_column(Date, nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    flight_number: Mapped[str | None] = mapped_column(String(80))
    airport: Mapped[str] = mapped_column(String(30), nullable=False)
    need_airport_pickup: Mapped[bool] = mapped_column(Boolean, nullable=False)
    products_services: Mapped[str] = mapped_column(Text, nullable=False)
    looking_for: Mapped[list] = mapped_column(JSON, nullable=False)
    preferred_countries: Mapped[list] = mapped_column(JSON, nullable=False)
    business_objectives: Mapped[str] = mapped_column(Text, nullable=False)
    activity_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    dietary_restrictions: Mapped[str | None] = mapped_column(Text)
    medical_condition: Mapped[str | None] = mapped_column(Text)
    special_assistance: Mapped[str | None] = mapped_column(Text)
    need_official_invoice: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(100))
    information_accuracy_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    terms_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    business_matching_data_consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    terms_version: Mapped[str] = mapped_column(String(40), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DelegateRegistrationPackageSelection(Base):
    __tablename__ = "delegate_registration_package_selections"
    __table_args__ = (UniqueConstraint("registration_id", "delegate_package_id", name="uq_registration_delegate_package"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False)
    delegate_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delegate_packages.id"), nullable=False)
    package_rate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delegate_package_rates.id"), nullable=False)
    selection_role: Mapped[str] = mapped_column(String(20), nullable=False)
    occupancy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    package_code: Mapped[str] = mapped_column(String(30), nullable=False)
    package_name: Mapped[str] = mapped_column(String(160), nullable=False)
    rate_name: Mapped[str] = mapped_column(String(120), nullable=False)
    selected_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    selected_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    selected_payment_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    payment_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccommodationTravel(Base):
    __tablename__ = "accommodation_travel"
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), primary_key=True)
    room_preference: Mapped[str] = mapped_column(String(80), nullable=False)
    preferred_roommate: Mapped[str | None] = mapped_column(String(255))
    arrival_date: Mapped[date] = mapped_column(Date, nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    flight_number: Mapped[str | None] = mapped_column(String(80))
    airport: Mapped[str] = mapped_column(String(30), nullable=False)
    need_airport_pickup: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RegistrationParticipationCategory(Base):
    __tablename__ = "registration_participation_categories"
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(40), primary_key=True)


class RegistrationActivity(Base):
    __tablename__ = "registration_activities"
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), primary_key=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_activities.id", ondelete="CASCADE"), primary_key=True)


class BusinessMatchingProfileSlot(Base):
    __tablename__ = "business_matching_profile_slots"
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_matching_profiles.id", ondelete="CASCADE"), primary_key=True)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_matching_slots.id", ondelete="CASCADE"), primary_key=True)


class RegistrationDocument(Base):
    __tablename__ = "registration_documents"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"))
    exhibitor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exhibitor_registrations.id", ondelete="CASCADE"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExhibitorRegistration(Base):
    __tablename__ = "exhibitor_registrations"
    __table_args__ = (UniqueConstraint("event_id", "participant_id", name="uq_exhibitor_event_participant"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    products_to_display: Mapped[str] = mapped_column(Text, nullable=False)
    booth_size_requested: Mapped[str] = mapped_column(String(80), nullable=False)
    electricity_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    special_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    exhibition_terms_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exhibition_terms_version: Mapped[str] = mapped_column(String(40), nullable=False)
    exhibition_terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
