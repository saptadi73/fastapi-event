"""add fixed IDR payment amount to delegate packages

Revision ID: 202608150014
Revises: 202608150013
"""
from alembic import op
import sqlalchemy as sa

revision = "202608150014"
down_revision = "202608150013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delegate_packages", sa.Column("payment_amount_idr", sa.Numeric(18, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("delegate_packages", "payment_amount_idr")
