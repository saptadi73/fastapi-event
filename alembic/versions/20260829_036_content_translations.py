"""add localized dynamic content translations

Revision ID: 202608290036
Revises: 202608290035
"""
import sqlalchemy as sa
from alembic import op

revision = "202608290036"
down_revision = "202608290035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", "locale", name="uq_content_translation_entity_locale"),
    )
    op.create_index("ix_content_translation_lookup", "content_translations", ["entity_type", "locale", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_content_translation_lookup", table_name="content_translations")
    op.drop_table("content_translations")
