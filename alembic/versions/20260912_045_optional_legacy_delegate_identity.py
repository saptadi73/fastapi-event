"""Retain legacy delegate identity without requiring duplicate profile input.

Revision ID: 202609120045
Revises: 202609040044
"""
from alembic import op

revision = "202609120045"
down_revision = "202609040044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for field in ("full_name", "title", "nationality", "email"):
        op.alter_column("delegate_registration_details", field, nullable=True)


def downgrade() -> None:
    # New registrations have no duplicate identity; preserve them on rollback.
    for field in ("full_name", "title", "nationality", "email"):
        op.execute(f"UPDATE delegate_registration_details SET {field} = '' WHERE {field} IS NULL")
        op.alter_column("delegate_registration_details", field, nullable=False)
