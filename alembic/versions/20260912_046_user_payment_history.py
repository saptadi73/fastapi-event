"""Allow users to hide unsuccessful attempts without affecting accounting."""
from alembic import op
import sqlalchemy as sa

revision = "202609120046"
down_revision = "202609120045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("hidden_from_user_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "hidden_from_user_at")
