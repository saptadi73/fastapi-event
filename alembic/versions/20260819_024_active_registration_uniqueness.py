"""allow a new registration after cancellation

Revision ID: 202608190024
Revises: 202608190023
"""

import sqlalchemy as sa
from alembic import op


revision = "202608190024"
down_revision = "202608190023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_registration_event_participant", "registrations", type_="unique")
    op.create_index(
        "uq_registration_active_event_participant",
        "registrations",
        ["event_id", "participant_id"],
        unique=True,
        postgresql_where=sa.text("lower(status) NOT IN ('canceled', 'cancelled')"),
    )


def downgrade() -> None:
    op.drop_index("uq_registration_active_event_participant", table_name="registrations")
    op.create_unique_constraint(
        "uq_registration_event_participant",
        "registrations",
        ["event_id", "participant_id"],
    )