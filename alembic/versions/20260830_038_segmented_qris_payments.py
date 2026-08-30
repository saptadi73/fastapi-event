"""add segmented QRIS payment metadata

Revision ID: 202608300038
Revises: 202608290037
"""
from alembic import op
import sqlalchemy as sa


revision = "202608300038"
down_revision = "202608290037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("payment_sequence", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("payment_sequence_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_payments_sequence_positive",
        "payments",
        "payment_sequence IS NULL OR payment_sequence > 0",
    )
    op.create_check_constraint(
        "ck_payments_sequence_count_valid",
        "payments",
        "payment_sequence_count IS NULL OR (payment_sequence_count > 0 AND payment_sequence <= payment_sequence_count)",
    )
    op.create_index("ix_payments_order_sequence", "payments", ["order_id", "payment_sequence"])


def downgrade() -> None:
    op.drop_index("ix_payments_order_sequence", table_name="payments")
    op.drop_constraint("ck_payments_sequence_count_valid", "payments", type_="check")
    op.drop_constraint("ck_payments_sequence_positive", "payments", type_="check")
    op.drop_column("payments", "payment_sequence_count")
    op.drop_column("payments", "payment_sequence")
