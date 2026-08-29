"""enforce supported bilingual locale values

Revision ID: 202608290037
Revises: 202608290036
"""
from alembic import op

revision = "202608290037"
down_revision = "202608290036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("ck_users_preferred_locale", "users", "preferred_locale IN ('en', 'zh-CN')")
    op.create_check_constraint("ck_email_template_locale", "email_notification_templates", "locale IN ('en', 'zh-CN')")
    op.create_check_constraint("ck_email_log_locale", "email_notification_logs", "locale IN ('en', 'zh-CN')")
    op.create_check_constraint("ck_content_translation_locale", "content_translations", "locale IN ('en', 'zh-CN')")


def downgrade() -> None:
    op.drop_constraint("ck_content_translation_locale", "content_translations", type_="check")
    op.drop_constraint("ck_email_log_locale", "email_notification_logs", type_="check")
    op.drop_constraint("ck_email_template_locale", "email_notification_templates", type_="check")
    op.drop_constraint("ck_users_preferred_locale", "users", type_="check")
