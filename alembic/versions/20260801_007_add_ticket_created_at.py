"""add ticket created_at column

Revision ID: 202608010007
Revises: 202608010006
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "202608010007"
down_revision = "202608010006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_column("tickets", "created_at")
