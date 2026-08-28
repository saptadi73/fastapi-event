"""add event ownership and soft-cancel metadata to orders

Revision ID: 202608280034
Revises: 202608270033
"""
import sqlalchemy as sa
from alembic import op

revision = "202608280034"
down_revision = "202608270033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("event_id", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("canceled_by", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_orders_event_id_events", "orders", "events", ["event_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_orders_canceled_by_users", "orders", "users", ["canceled_by"], ["id"], ondelete="SET NULL"
    )
    op.execute(sa.text(
        """UPDATE orders AS o SET event_id = r.event_id
           FROM registrations AS r
           WHERE o.registration_id = r.id AND o.event_id IS NULL"""
    ))
    op.execute(sa.text(
        """UPDATE orders AS o SET event_id = p.event_id
           FROM order_items AS oi JOIN products AS p ON p.id = oi.product_id
           WHERE oi.order_id = o.id AND o.event_id IS NULL"""
    ))
    op.create_index("ix_orders_user_status_created", "orders", ["user_id", "status", "created_at"])
    op.create_index("ix_orders_event_id", "orders", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_event_id", table_name="orders")
    op.drop_index("ix_orders_user_status_created", table_name="orders")
    op.drop_constraint("fk_orders_canceled_by_users", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_event_id_events", "orders", type_="foreignkey")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "canceled_by")
    op.drop_column("orders", "canceled_at")
    op.drop_column("orders", "event_id")
