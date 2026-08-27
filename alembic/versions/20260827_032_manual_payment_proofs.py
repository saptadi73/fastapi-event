"""manual payment proof uploads

Revision ID: 202608270032
Revises: 202608250031
"""
import sqlalchemy as sa
from alembic import op

revision = "202608270032"
down_revision = "202608250031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_proofs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_payment_proofs_payment_id", "payment_proofs", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_proofs_payment_id", table_name="payment_proofs")
    op.drop_table("payment_proofs")
