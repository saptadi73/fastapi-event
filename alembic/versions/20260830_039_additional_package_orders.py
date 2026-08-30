"""support post-registration additional package orders

Revision ID: 202608300039
Revises: 202608300038
"""
from alembic import op
import sqlalchemy as sa


revision = "202608300039"
down_revision = "202608300038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("order_kind", sa.String(length=30), nullable=False, server_default="legacy"))
    op.create_check_constraint(
        "ck_orders_order_kind",
        "orders",
        "order_kind IN ('legacy', 'main_registration', 'additional', 'exhibitor')",
    )
    op.create_index("ix_orders_registration_kind_status", "orders", ["registration_id", "order_kind", "status"])
    op.add_column(
        "delegate_registration_package_selections",
        sa.Column("source_order_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_delegate_selection_source_order",
        "delegate_registration_package_selections",
        "orders",
        ["source_order_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_delegate_selection_source_order", "delegate_registration_package_selections", type_="foreignkey")
    op.drop_column("delegate_registration_package_selections", "source_order_id")
    op.drop_index("ix_orders_registration_kind_status", table_name="orders")
    op.drop_constraint("ck_orders_order_kind", "orders", type_="check")
    op.drop_column("orders", "order_kind")
