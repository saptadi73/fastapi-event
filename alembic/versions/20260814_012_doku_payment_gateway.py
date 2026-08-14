"""replace payment gateway integration with DOKU Checkout

Revision ID: 202608140012
Revises: 202608140011
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "202608140012"
down_revision = "202608140011"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("payments", sa.Column("checkout_url", sa.Text(), nullable=True))
    op.alter_column("payments", "provider", server_default="doku")
    op.execute("UPDATE payments SET provider = 'doku', payment_type = 'doku_checkout' WHERE provider = 'midtrans'")
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("event_status", sa.String(40), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "request_id", name="uq_payment_webhook_provider_request"),
    )

def downgrade() -> None:
    op.drop_table("payment_webhook_events")
    op.drop_column("payments", "checkout_url")
    op.alter_column("payments", "provider", server_default="midtrans")
