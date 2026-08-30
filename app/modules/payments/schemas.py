from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CreateDokuCheckoutRequest(BaseModel):
    registration_id: UUID | None = None
    order_id: UUID | None = None

    @model_validator(mode="after")
    def validate_payment_source(self):
        if (self.registration_id is None) == (self.order_id is None):
            raise ValueError("Exactly one of registration_id or order_id must be provided")
        return self


class ContinueOrderPaymentRequest(BaseModel):
    provider: Literal["doku", "midtrans"]


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ManualPaymentConfirmRequest(BaseModel):
    payment_method: Literal["manual_transfer", "manual_qr_code"] = "manual_transfer"
    transfer_reference: str = Field(min_length=3, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)
    paid_at: datetime | None = None


class OfflineRegistrationPaymentRequest(BaseModel):
    payment_method: Literal["cash", "manual_transfer", "manual_qr_code", "edc", "other_offline"]
    amount: float | None = Field(default=None, gt=0)
    currency: Literal["IDR"] = "IDR"
    receipt_number: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._~/-]+$")
    paid_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class TransactionStatusUpdateRequest(BaseModel):
    status: Literal["paid", "success", "canceled"]
    notes: str | None = Field(default=None, max_length=1000)
    paid_at: datetime | None = None


class TransactionBulkActionRequest(BaseModel):
    payment_ids: list[UUID] = Field(min_length=1, max_length=500)
    action: Literal["paid", "success", "canceled", "delete"]
    notes: str | None = Field(default=None, max_length=1000)
    paid_at: datetime | None = None

    @model_validator(mode="after")
    def validate_unique_payment_ids(self):
        if len(set(self.payment_ids)) != len(self.payment_ids):
            raise ValueError("payment_ids must not contain duplicates")
        return self


class PaymentProofRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_id: UUID
    uploaded_by: UUID
    original_filename: str
    mime_type: str
    file_size: int
    notes: str | None = None
    created_at: datetime


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
    registration_id: UUID | None
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
    payment_sequence: int | None = None
    payment_sequence_count: int | None = None
    paid_amount: float = 0
    remaining_amount: float = 0


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
    payment_sequence: int | None = None
    payment_sequence_count: int | None = None
    payment_amount: float | None = None
    paid_amount: float = 0
    remaining_amount: float = 0


class MidtransCheckoutResponse(DokuCheckoutResponse):
    token: str


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registration_id: UUID | None
    event_id: UUID | None = None
    order_number: str
    order_kind: str = "legacy"
    subtotal: float
    discount_amount: float
    tax_amount: float
    service_fee: float
    total_amount: float
    currency: str
    status: str
    expires_at: datetime | None = None
    canceled_at: datetime | None = None
    canceled_by: UUID | None = None
    cancellation_reason: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)

    @field_validator("order_kind", mode="before")
    @classmethod
    def normalize_order_kind(cls, value):
        return value or "legacy"


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    provider: str
    provider_transaction_id: str | None = None
    provider_order_id: str | None = None
    payment_type: str | None = None
    gross_amount: float
    payment_sequence: int | None = None
    payment_sequence_count: int | None = None
    currency: str
    transaction_status: str
    fraud_status: str | None = None
    paid_at: datetime | None = None
    checkout_url: str | None = None
    channel_code: str | None = None
    virtual_account_no: str | None = None
    provider_reference_no: str | None = None
    offline_receipt_number: str | None = None
    confirmed_by: UUID | None = None
    payment_instructions_url: str | None = None
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None
    deletion_reason: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)


class OrderItemRead(BaseModel):
    id: UUID
    product_id: UUID | None = None
    product_code: str
    product_name: str
    product_type: str
    quantity: int
    unit_price: float
    currency: str
    line_total: float
    metadata: dict = Field(default_factory=dict)


class UserOrderDetail(BaseModel):
    order: OrderRead
    items: list[OrderItemRead]
    latest_payment: PaymentRead | None = None
    payment_attempts: list[PaymentRead] = Field(default_factory=list)
    paid_amount: float = 0
    remaining_amount: float = 0
    is_payment_complete: bool = False


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
