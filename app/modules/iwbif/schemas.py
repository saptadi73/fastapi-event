from datetime import date, datetime, time
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from .constants import *


class DelegateRegistrationWrite(BaseModel):
    # Optional for backward compatibility. The backend always resolves the
    # participant from the authenticated user and rejects a mismatched ID.
    participant_id: UUID | None = None
    # Resolved by the backend from the authenticated user's purchased Delegate
    # order. Kept optional for backward-compatible clients only.
    delegate_package_id: UUID | None = None
    full_name: str = Field(min_length=2, max_length=255)
    job_title: str = Field(min_length=1, max_length=160)
    company_organization: str = Field(min_length=1, max_length=255)
    nationality: str = Field(min_length=1, max_length=100)
    title: str
    business_sector: str
    email: str
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
        allowed = [(self.business_sector, BUSINESS_SECTORS, "business_sector"), (self.room_preference, ROOM_PREFERENCES, "room_preference"), (self.airport, AIRPORTS, "airport")]
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
    id: UUID; event_id: UUID; code: str; name: str; package_type: str; selection_mode: str; description: str | None = None; display_order: int; currency: str; amount: float; payment_amount_idr: float | None = None; is_active: bool
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
    package_type: str = Field(default="main", pattern="^(main|additional|exhibitor)$")
    selection_mode: str = Field(default="required_one", pattern="^(required_one|optional)$")
    description: str | None = Field(default=None, max_length=3000)
    display_order: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    amount: float = Field(gt=0)
    payment_amount_idr: float | None = Field(default=None, gt=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_selection_mode(self):
        expected = "required_one" if self.package_type == "main" else "optional"
        if self.selection_mode != expected:
            raise ValueError(f"{self.package_type} package must use selection_mode={expected}")
        return self


class PackageRateWrite(BaseModel):
    occupancy_type: str = Field(pattern="^(sharing|single|standard)$")
    name: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_amount_idr: float | None = Field(default=None, gt=0)
    is_default: bool = False
    is_active: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_validity(self):
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        if self.is_default and not self.is_active:
            raise ValueError("default rate must be active")
        return self


class PackageRateRead(PackageRateWrite):
    id: UUID
    delegate_package_id: UUID
    product_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)


class PackageFacilityWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    unit: str | None = Field(default=None, max_length=40)
    pricing_mode: str = Field(default="included", pattern="^(included|separately_priced)$")
    sharing_amount: float | None = Field(default=None, ge=0)
    single_amount: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_pricing(self):
        if self.pricing_mode == "separately_priced" and self.sharing_amount is None and self.single_amount is None:
            raise ValueError("separately priced facility requires sharing_amount or single_amount")
        return self


class PackageFacilityRead(PackageFacilityWrite):
    id: UUID
    delegate_package_id: UUID
    model_config = ConfigDict(from_attributes=True)


class PackageCatalogItem(PackageRead):
    rates: list[PackageRateRead] = Field(default_factory=list)
    facilities: list[PackageFacilityRead] = Field(default_factory=list)


class PackageCatalogRead(BaseModel):
    main_packages: list[PackageCatalogItem]
    additional_packages: list[PackageCatalogItem]
    exhibitor_packages: list[PackageCatalogItem] = Field(default_factory=list)

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
    company_name: str = Field(min_length=1); brand: str = Field(min_length=1); contact_person: str = Field(min_length=1)
    products_to_display: str = Field(min_length=1)
    booth_size_requested: str; electricity_requirement: str = Field(min_length=1); special_requirement: str = Field(min_length=1)
    exhibition_terms_accepted: bool; exhibition_terms_version: str = Field(min_length=1)
    @model_validator(mode="after")
    def validate_values(self):
        if self.booth_size_requested not in BOOTH_SIZES: raise ValueError("Select a booth number between 1 and 40")
        if not self.exhibition_terms_accepted: raise ValueError("Exhibition terms must be accepted")
        return self

class ExhibitorRead(ExhibitorWrite):
    email: str
    id: UUID; event_id: UUID; status: str; created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_values(self):
        # Historical booth sizes must remain readable so owners can update them.
        return self

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
