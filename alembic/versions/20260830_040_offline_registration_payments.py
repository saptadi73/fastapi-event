"""add auditable offline registration payments

Revision ID: 202608300040
Revises: 202608300039
"""
from alembic import op
import sqlalchemy as sa


revision = "202608300040"
down_revision = "202608300039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("offline_receipt_number", sa.String(length=100), nullable=True))
    op.add_column("payments", sa.Column("confirmed_by", sa.Uuid(), nullable=True))
    op.create_unique_constraint("uq_payments_offline_receipt", "payments", ["offline_receipt_number"])
    op.create_foreign_key(
        "fk_payments_confirmed_by_users",
        "payments",
        "users",
        ["confirmed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_confirmed_by_users", "payments", type_="foreignkey")
    op.drop_constraint("uq_payments_offline_receipt", "payments", type_="unique")
    op.drop_column("payments", "confirmed_by")
    op.drop_column("payments", "offline_receipt_number")
