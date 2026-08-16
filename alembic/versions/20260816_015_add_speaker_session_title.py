"""add speaker session title

Revision ID: 202608160015
Revises: 202608150014
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa


revision = "202608160015"
down_revision = "202608150014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("speakers", sa.Column("session_title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("speakers", "session_title")
