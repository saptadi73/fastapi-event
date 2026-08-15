import uuid

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderStatus(str):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELED = "canceled"


class PaymentStatus(str):
    CREATED = "created"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    service_fee: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.DRAFT)
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="doku")
    provider_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    transaction_status: Mapped[str] = mapped_column(String(30), default=PaymentStatus.CREATED)
    fraud_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    signature_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    virtual_account_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_instructions_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "request_id", name="uq_payment_webhook_provider_request"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
