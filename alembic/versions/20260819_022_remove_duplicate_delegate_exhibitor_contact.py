"""remove duplicate country and phone fields from IWBIF registrations

Revision ID: 202608190022
Revises: 202608190021
"""

import sqlalchemy as sa
from alembic import op


revision = "202608190022"
down_revision = "202608190021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("delegate_registration_details", "country")
    op.drop_column("delegate_registration_details", "mobile_whatsapp")
    op.drop_column("exhibitor_registrations", "country")
    op.drop_column("exhibitor_registrations", "phone")


def downgrade() -> None:
    op.add_column("delegate_registration_details", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("delegate_registration_details", sa.Column("mobile_whatsapp", sa.String(60), nullable=True))
    op.add_column("exhibitor_registrations", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("exhibitor_registrations", sa.Column("phone", sa.String(60), nullable=True))
