"""add initial account registration fields and progress status

Revision ID: 202608190019
Revises: 202608170018
"""

import sqlalchemy as sa
from alembic import op


revision = "202608190019"
down_revision = "202608170018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column(
        "users",
        sa.Column("registration_status", sa.String(length=40), nullable=False, server_default="account_created"),
    )
    op.execute("UPDATE users SET country = 'Unknown' WHERE country IS NULL")
    op.alter_column("users", "country", nullable=False)
    op.alter_column("users", "full_name", nullable=True)


def downgrade() -> None:
    op.alter_column("users", "full_name", nullable=False)
    op.drop_column("users", "registration_status")
    op.drop_column("users", "country")
