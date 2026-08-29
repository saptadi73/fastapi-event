"""add English and Simplified Chinese locale support

Revision ID: 202608290035
Revises: 202608280034
"""
import sqlalchemy as sa
from alembic import op

revision = "202608290035"
down_revision = "202608280034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_locale", sa.String(length=10), nullable=False, server_default="en"))
    op.add_column("email_notification_templates", sa.Column("locale", sa.String(length=10), nullable=False, server_default="en"))
    op.add_column("email_notification_logs", sa.Column("locale", sa.String(length=10), nullable=False, server_default="en"))
    op.drop_constraint("uq_email_template_event_trigger", "email_notification_templates", type_="unique")
    op.create_unique_constraint(
        "uq_email_template_event_trigger_locale",
        "email_notification_templates",
        ["event_id", "trigger", "locale"],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM email_notification_templates WHERE locale <> 'en'"))
    op.drop_constraint("uq_email_template_event_trigger_locale", "email_notification_templates", type_="unique")
    op.create_unique_constraint("uq_email_template_event_trigger", "email_notification_templates", ["event_id", "trigger"])
    op.drop_column("email_notification_logs", "locale")
    op.drop_column("email_notification_templates", "locale")
    op.drop_column("users", "preferred_locale")
