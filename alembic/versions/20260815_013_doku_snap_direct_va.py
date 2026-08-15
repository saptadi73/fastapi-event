"""add DOKU SNAP direct VA payment fields

Revision ID: 202608150013
Revises: 202608140012
"""
from alembic import op
import sqlalchemy as sa

revision = "202608150013"
down_revision = "202608140012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("channel_code", sa.String(40), nullable=True))
    op.add_column("payments", sa.Column("virtual_account_no", sa.String(40), nullable=True))
    op.add_column("payments", sa.Column("provider_reference_no", sa.String(128), nullable=True))
    op.add_column("payments", sa.Column("external_id", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("payment_instructions_url", sa.Text(), nullable=True))
    op.create_index("ix_payments_virtual_account_no", "payments", ["virtual_account_no"])
    op.create_index("ix_payments_external_id", "payments", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_external_id", table_name="payments")
    op.drop_index("ix_payments_virtual_account_no", table_name="payments")
    op.drop_column("payments", "payment_instructions_url")
    op.drop_column("payments", "external_id")
    op.drop_column("payments", "provider_reference_no")
    op.drop_column("payments", "virtual_account_no")
    op.drop_column("payments", "channel_code")
