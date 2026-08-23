"""bridge legacy database revision into the canonical migration chain

Revision ID: 202608200001
Revises: 202608190024

Some existing databases were stamped with ``202608200001`` after applying
the schema changes through ``202608190024``.  Keep that historical marker in
the graph so those databases can continue upgrading without restamping.
"""


revision = "202608200001"
down_revision = "202608190024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
