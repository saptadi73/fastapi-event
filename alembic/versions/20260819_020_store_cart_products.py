"""add product catalog, carts and order line items

Revision ID: 202608190020
Revises: 202608190019
"""

import sqlalchemy as sa
from alembic import op


revision = "202608190020"
down_revision = "202608190019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    op.execute("""
        UPDATE orders o
        SET user_id = p.user_id
        FROM registrations r
        JOIN participants p ON p.id = r.participant_id
        WHERE o.registration_id = r.id AND o.user_id IS NULL
    """)
    op.alter_column("orders", "user_id", nullable=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("product_type", sa.String(30), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("max_quantity", sa.Integer()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "code", name="uq_product_event_code"),
    )
    op.create_table(
        "carts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "event_id", name="uq_cart_user_event"),
    )
    op.create_table(
        "cart_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cart_id", sa.Uuid(), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("product_code", sa.String(60), nullable=False),
        sa.Column("product_name", sa.String(180), nullable=False),
        sa.Column("product_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("products")
    op.drop_column("orders", "user_id")
