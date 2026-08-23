"""capture raw Midtrans webhook requests

Revision ID: 202608230029
Revises: 202608230028
"""

import sqlalchemy as sa
from alembic import op


revision = "202608230029"
down_revision = "202608230028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_webhook_captures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("raw_body", sa.Text(), nullable=False),
        sa.Column("parsed_payload", sa.JSON(), nullable=True),
        sa.Column("processing_status", sa.String(20), server_default="received", nullable=False),
        sa.Column("processing_result", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_capture_provider_received",
        "payment_webhook_captures",
        ["provider", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_capture_provider_received", table_name="payment_webhook_captures")
    op.drop_table("payment_webhook_captures")
