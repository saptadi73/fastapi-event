from datetime import date, datetime, time
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from .constants import *


class DelegateRegistrationWrite(BaseModel):
    # Optional for backward compatibility. The backend always resolves the
    # participant from the authenticated user and rejects a mismatched ID.
    participant_id: UUID | None = None
    delegate_package_id: UUID
    full_name: str = Field(min_length=2, max_length=255)
    job_title: str = Field(min_length=1, max_length=160)
    company_organization: str = Field(min_length=1, max_length=255)
    nationality: str = Field(min_length=1, max_length=100)
    title: str
    business_sector: str
    country: str
    email: str
    mobile_whatsapp: str = Field(min_length=5, max_length=60)
    office_phone: str | None = None
    company_website: HttpUrl | None = None
    linkedin: HttpUrl | None = None
    company_address: str = Field(min_length=3)
    participation_categories: list[str] = Field(min_length=1)
    presentation_topic: str | None = None
    products_interested: str | None = None
    investment_interest: str | None = None
    room_preference: str
    preferred_roommate: str | None = None
    arrival_date: date
    departure_date: date
    flight_number: str | None = None
    airport: str
    need_airport_pickup: bool
    products_services: str = Field(min_length=1)
    looking_for: list[str] = Field(min_length=1)
    preferred_countries: list[str] = Field(min_length=1)
    business_objectives: str = Field(min_length=1)
    activity_ids: list[UUID] = Field(min_length=1)
    dietary_restrictions: str | None = None
    medical_condition: str | None = None
    special_assistance: str | None = None
    preferred_payment_method: str
    need_official_invoice: bool
    tax_id: str | None = None
    information_accuracy_confirmed: bool
    terms_accepted: bool
    business_matching_data_consent: bool
    terms_version: str = Field(min_length=1, max_length=40)
    consent_version: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_source_rules(self):
        if "@" not in self.email or self.email.startswith("@") or self.email.endswith("@"): raise ValueError("Invalid email")
        allowed = [(self.business_sector, BUSINESS_SECTORS, "business_sector"), (self.country, COUNTRIES, "country"), (self.room_preference, ROOM_PREFERENCES, "room_preference"), (self.airport, AIRPORTS, "airport"), (self.preferred_payment_method, PAYMENT_METHODS, "preferred_payment_method")]
        for value, choices, name in allowed:
            if value not in choices: raise ValueError(f"Invalid {name}")
        for values, choices, name in [(self.participation_categories, PARTICIPATION_CATEGORIES, "participation_categories"), (self.looking_for, LOOKING_FOR, "looking_for"), (self.preferred_countries, PREFERRED_COUNTRIES, "preferred_countries")]:
            if not set(values).issubset(choices): raise ValueError(f"Invalid {name}")
            if len(values) != len(set(values)): raise ValueError(f"Duplicate {name}")
        if len(self.activity_ids) != len(set(self.activity_ids)): raise ValueError("Duplicate activity_ids")
        if self.departure_date < self.arrival_date: raise ValueError("departure_date must be on or after arrival_date")
        if not all((self.information_accuracy_confirmed, self.terms_accepted, self.business_matching_data_consent)): raise ValueError("All declarations and consents must be accepted")
        return self


class DelegateRegistrationRead(BaseModel):
    id: UUID
    event_id: UUID
    participant_id: UUID
    registration_number: str
    status: str
    detail: dict


class PackageRead(BaseModel):
    id: UUID; event_id: UUID; code: str; name: str; currency: str; amount: float; payment_amount_idr: float | None = None; is_active: bool
    model_config = ConfigDict(from_attributes=True)

class ActivityRead(BaseModel):
    id: UUID; event_id: UUID; name: str; is_active: bool
    model_config = ConfigDict(from_attributes=True)

class SlotRead(BaseModel):
    id: UUID; event_id: UUID; slot_date: date; start_time: time; end_time: time; label: str; capacity: int; is_active: bool
    model_config = ConfigDict(from_attributes=True)

class PackageWrite(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=160)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    amount: float = Field(gt=0)
    payment_amount_idr: float | None = Field(default=None, gt=0)
    is_active: bool = True

class ActivityWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    is_active: bool = True

class SlotWrite(BaseModel):
    slot_date: date
    start_time: time
    end_time: time
    label: str = Field(min_length=1, max_length=120)
    capacity: int = Field(ge=0)
    is_active: bool = True
    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time <= self.start_time: raise ValueError("end_time must be after start_time")
        return self

class ExhibitorWrite(BaseModel):
    participant_id: UUID | None = None
    company_name: str = Field(min_length=1); country: str; brand: str = Field(min_length=1); contact_person: str = Field(min_length=1)
    email: str; phone: str = Field(min_length=5); products_to_display: str = Field(min_length=1)
    booth_size_requested: str; electricity_requirement: str = Field(min_length=1); special_requirement: str = Field(min_length=1)
    exhibition_terms_accepted: bool; exhibition_terms_version: str = Field(min_length=1)
    @model_validator(mode="after")
    def validate_values(self):
        if "@" not in self.email or self.email.startswith("@") or self.email.endswith("@"): raise ValueError("Invalid email")
        if self.country not in COUNTRIES or self.booth_size_requested not in BOOTH_SIZES: raise ValueError("Invalid country or booth size")
        if not self.exhibition_terms_accepted: raise ValueError("Exhibition terms must be accepted")
        return self

class ExhibitorRead(ExhibitorWrite):
    id: UUID; event_id: UUID; status: str; created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MatchingProfileWrite(BaseModel):
    company_name: str = Field(min_length=1); country: str = Field(min_length=1); representative: str = Field(min_length=1)
    email: str; phone: str = Field(min_length=5); products: str = Field(min_length=1); services: str = Field(min_length=1)
    hs_code: str = Field(min_length=1); production_capacity: str = Field(min_length=1); certificates: str = Field(min_length=1)
    markets_served: str = Field(min_length=1); looking_for: list[str] = Field(min_length=1); preferred_countries: list[str] = Field(min_length=1)
    preferred_slot_ids: list[UUID] = Field(min_length=1); estimated_deal_investment_value: str = Field(min_length=1)
    additional_notes: str = Field(min_length=1); profile_sharing_consent: bool
    @model_validator(mode="after")
    def validate_values(self):
        if "@" not in self.email or self.email.startswith("@") or self.email.endswith("@"): raise ValueError("Invalid email")
        if not set(self.looking_for).issubset(LOOKING_FOR) or not set(self.preferred_countries).issubset(PREFERRED_COUNTRIES): raise ValueError("Invalid matching selection")
        if len(self.looking_for) != len(set(self.looking_for)) or len(self.preferred_countries) != len(set(self.preferred_countries)) or len(self.preferred_slot_ids) != len(set(self.preferred_slot_ids)): raise ValueError("Duplicate matching selection")
        if not self.profile_sharing_consent: raise ValueError("Profile sharing consent must be accepted")
        return self
