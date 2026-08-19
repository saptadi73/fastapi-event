"""remove payment method from delegate registration form

Revision ID: 202608190023
Revises: 202608190022
"""

import sqlalchemy as sa
from alembic import op


revision = "202608190023"
down_revision = "202608190022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("delegate_registration_details", "preferred_payment_method")


def downgrade() -> None:
    op.add_column("delegate_registration_details", sa.Column("preferred_payment_method", sa.String(40), nullable=True))
