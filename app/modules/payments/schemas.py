from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateMidtransRequest(BaseModel):
    registration_id: UUID | None = None


class MidtransCreateResponse(BaseModel):
    snap_token: str
    redirect_url: str
    already_paid: bool = False
    payment_id: UUID | None = None
    order_status: str | None = None
    requires_payment: bool = True


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registration_id: UUID
    order_number: str
    subtotal: float
    discount_amount: float
    tax_amount: float
    service_fee: float
    total_amount: float
    currency: str
    status: str
    expires_at: datetime | None = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    provider: str
    provider_transaction_id: str | None = None
    provider_order_id: str | None = None
    payment_type: str | None = None
    gross_amount: float
    currency: str
    transaction_status: str
    fraud_status: str | None = None
    paid_at: datetime | None = None


class InvoiceRegistration(BaseModel):
    id: UUID
    registration_number: str
    status: str
    event_id: UUID
    event_name: str | None = None
    participant_id: UUID
    delegate_package_id: UUID | None = None
    delegate_package_code: str | None = None
    delegate_package_name: str | None = None
    confirmed_at: datetime | None = None


class InvoiceParticipant(BaseModel):
    id: UUID
    full_name: str
    organization_name: str | None = None
    email: str


class InvoiceRead(BaseModel):
    registration: InvoiceRegistration
    participant: InvoiceParticipant
    order: OrderRead | None = None
    payment: PaymentRead | None = None
