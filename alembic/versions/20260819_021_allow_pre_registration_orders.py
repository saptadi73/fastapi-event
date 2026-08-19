"""allow store checkout before event registration

Revision ID: 202608190021
Revises: 202608190020
"""

import sqlalchemy as sa
from alembic import op


revision = "202608190021"
down_revision = "202608190020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("orders", "registration_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM orders WHERE registration_id IS NULL")
    op.alter_column("orders", "registration_id", existing_type=sa.Uuid(), nullable=False)
