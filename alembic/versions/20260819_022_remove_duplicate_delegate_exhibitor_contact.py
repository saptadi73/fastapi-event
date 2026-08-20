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
    op.execute("ALTER TABLE delegate_registration_details DROP COLUMN IF EXISTS country")
    op.execute("ALTER TABLE delegate_registration_details DROP COLUMN IF EXISTS mobile_whatsapp")
    op.execute("ALTER TABLE exhibitor_registrations DROP COLUMN IF EXISTS country")
    op.execute("ALTER TABLE exhibitor_registrations DROP COLUMN IF EXISTS phone")


def downgrade() -> None:
    op.add_column("delegate_registration_details", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("delegate_registration_details", sa.Column("mobile_whatsapp", sa.String(60), nullable=True))
    op.add_column("exhibitor_registrations", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("exhibitor_registrations", sa.Column("phone", sa.String(60), nullable=True))
