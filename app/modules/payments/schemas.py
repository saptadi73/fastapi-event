from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateMidtransRequest(BaseModel):
    registration_id: UUID


class MidtransCreateResponse(BaseModel):
    snap_token: str
    redirect_url: str


class OrderRead(BaseModel):
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

