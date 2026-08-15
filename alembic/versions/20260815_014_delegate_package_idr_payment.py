"""add fixed IDR payment amount to delegate packages

Revision ID: 202608150014
Revises: 202608150013
"""
from alembic import op

revision = "202608150014"
down_revision = "202608150013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migration 010 creates this table from the current SQLAlchemy metadata.
    # On fresh databases that metadata may already include this column, while
    # older databases still need it added here.
    op.execute(
        "ALTER TABLE delegate_packages "
        "ADD COLUMN IF NOT EXISTS payment_amount_idr NUMERIC(18, 2)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE delegate_packages "
        "DROP COLUMN IF EXISTS payment_amount_idr"
    )
