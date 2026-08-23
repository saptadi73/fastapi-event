"""organizer-managed email preferences per account

Revision ID: 202608230028
Revises: 202608220027
"""

import sqlalchemy as sa
from alembic import op


revision = "202608230028"
down_revision = "202608220027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(60), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", "trigger", name="uq_email_preference_event_user_trigger"),
    )
    op.create_index(
        "ix_email_preference_event_user",
        "email_notification_preferences",
        ["event_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_preference_event_user", table_name="email_notification_preferences")
    op.drop_table("email_notification_preferences")
