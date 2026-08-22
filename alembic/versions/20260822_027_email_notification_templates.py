"""admin-managed email notification templates

Revision ID: 202608220027
Revises: 202608210026
Create Date: 2026-08-22
"""

import sqlalchemy as sa
from alembic import op

revision = "202608220027"
down_revision = "202608210026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_notification_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(60), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("subject_template", sa.String(255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("available_variables", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "trigger", name="uq_email_template_event_trigger"),
    )
    op.create_table(
        "email_notification_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("trigger", sa.String(60), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["email_notification_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_notification_logs_event_created", "email_notification_logs", ["event_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_notification_logs_event_created", table_name="email_notification_logs")
    op.drop_table("email_notification_logs")
    op.drop_table("email_notification_templates")
