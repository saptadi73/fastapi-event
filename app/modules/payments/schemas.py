from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateDokuCheckoutRequest(BaseModel):
    registration_id: UUID | None = None
    order_id: UUID | None = None


class PaymentChannelWrite(BaseModel):
    provider: str = "doku"
    code: str
    category: str
    display_name: str
    logo_url: str | None = None
    config_key: str | None = None
    merchant_id: str | None = None
    sub_merchant_id: str | None = None
    terminal_id: str | None = None
    is_enabled: bool = False
    sort_order: int = Field(default=100, ge=0)


class PaymentChannelRead(PaymentChannelWrite):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class PublicPaymentMethodRead(BaseModel):
    id: UUID
    provider: str
    code: str
    category: str
    display_name: str
    logo_url: str | None = None
    sort_order: int


class CreateDokuDirectVARequest(BaseModel):
    registration_id: UUID
    bank_code: str


class CreateDokuQrisRequest(BaseModel):
    registration_id: UUID


class DokuQrisResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    order_number: str
    status: str
    qr_content: str
    amount: float
    currency: str
    expires_at: datetime | None = None


class CreateDirectDebitBindingRequest(BaseModel):
    registration_id: UUID
    channel_code: str
    phone_no: str
    device_id: str | None = None


class DirectDebitBindingResponse(BaseModel):
    binding_id: UUID
    channel_code: str
    status: str
    redirect_url: str | None = None


class CreateDirectDebitPaymentRequest(BaseModel):
    registration_id: UUID
    binding_id: UUID


class DirectDebitPaymentResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    partner_reference_no: str
    status: str
    redirect_url: str | None = None


class VerifyDirectDebitOtpRequest(BaseModel):
    binding_id: UUID
    otp: str


class DokuDirectVAResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    order_number: str
    status: str
    bank_code: str
    virtual_account_no: str
    amount: float
    currency: str
    expires_at: datetime | None = None
    instructions_url: str | None = None


class DokuCheckoutResponse(BaseModel):
    payment_url: str
    token: str | None = None
    expires_at: datetime | None = None
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
    checkout_url: str | None = None
    channel_code: str | None = None
    virtual_account_no: str | None = None
    provider_reference_no: str | None = None
    payment_instructions_url: str | None = None


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
