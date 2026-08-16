"""enforce one exhibitor registration per user and event

Revision ID: 202608160017
Revises: 202608160016
Create Date: 2026-08-16
"""

from alembic import op


revision = "202608160017"
down_revision = "202608160016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_exhibitor_event_participant') THEN
            ALTER TABLE exhibitor_registrations
              ADD CONSTRAINT uq_exhibitor_event_participant UNIQUE (event_id, participant_id);
          END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE exhibitor_registrations DROP CONSTRAINT IF EXISTS uq_exhibitor_event_participant")
