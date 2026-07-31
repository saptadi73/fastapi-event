"""add payments and tickets tables

Revision ID: 202608010003
Revises: 202608010002
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "202608010003"
down_revision = "202608010002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("registration_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False, unique=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("service_fee", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="IDR"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"], name="fk_orders_registrations"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("order_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="midtrans"),
        sa.Column("provider_transaction_id", sa.String(length=100), nullable=True),
        sa.Column("provider_order_id", sa.String(length=100), nullable=True),
        sa.Column("payment_type", sa.String(length=60), nullable=True),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="IDR"),
        sa.Column("transaction_status", sa.String(length=30), nullable=False),
        sa.Column("fraud_status", sa.String(length=30), nullable=True),
        sa.Column("signature_key", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expired_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_payments_orders"),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("registration_id", sa.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("ticket_number", sa.String(length=40), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"], name="fk_tickets_registrations"),
    )

    op.create_table(
        "qr_tokens",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=256), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_qr_tokens_tickets"),
    )


def downgrade() -> None:
    op.drop_table("qr_tokens")
    op.drop_table("tickets")
    op.drop_table("payments")
    op.drop_table("orders")

