"""add SNAP direct debit account bindings

Revision ID: 202608170014
Revises: 202608150013
"""
from alembic import op
import sqlalchemy as sa

revision = "202608170014"
down_revision = "202608150013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_debit_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("channel_code", sa.String(length=40), nullable=False),
        sa.Column("customer_reference", sa.String(length=64), nullable=False),
        sa.Column("provider_reference_no", sa.String(length=128), nullable=True),
        sa.Column("token_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("participant_id", "channel_code", "token_id", name="uq_direct_debit_binding_token"),
    )
    op.create_index("ix_direct_debit_bindings_participant_channel", "direct_debit_bindings", ["participant_id", "channel_code"])


def downgrade() -> None:
    op.drop_index("ix_direct_debit_bindings_participant_channel", table_name="direct_debit_bindings")
    op.drop_table("direct_debit_bindings")
