"""add payment soft-delete metadata

Revision ID: 202608270033
Revises: 202608270032
"""
import sqlalchemy as sa
from alembic import op

revision = "202608270033"
down_revision = "202608270032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("deleted_by", sa.Uuid(), nullable=True))
    op.add_column("payments", sa.Column("deletion_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_payments_deleted_by_users", "payments", "users", ["deleted_by"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_payments_deleted_at", "payments", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_deleted_at", table_name="payments")
    op.drop_constraint("fk_payments_deleted_by_users", "payments", type_="foreignkey")
    op.drop_column("payments", "deletion_reason")
    op.drop_column("payments", "deleted_by")
    op.drop_column("payments", "deleted_at")
