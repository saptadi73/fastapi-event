"""merge payment catalog and IWBIF migration heads

Revision ID: 202608170018
Revises: 202608160017, 202608170015
"""

revision = "202608170018"
down_revision = ("202608160017", "202608170015")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge revision; schema changes are contained in both parent branches."""


def downgrade() -> None:
    """Merge revision; downgrading splits back into the parent branches."""
