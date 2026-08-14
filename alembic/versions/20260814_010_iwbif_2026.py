"""IWBIF 2026 delegate and exhibitor domain

Revision ID: 202608140010
Revises: 202608140009
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa
from app.modules.iwbif.models import BusinessMatchingSlot, DelegatePackage, DelegateRegistrationDetail, EventActivity, ExhibitorRegistration, RegistrationDocument

revision = "202608140010"
down_revision = "202608140009"
branch_labels = None
depends_on = None

TABLES = [DelegatePackage.__table__, EventActivity.__table__, BusinessMatchingSlot.__table__, DelegateRegistrationDetail.__table__, ExhibitorRegistration.__table__, RegistrationDocument.__table__]

def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES: table.create(bind, checkfirst=True)
    # IF NOT EXISTS keeps this migration valid both after the original v009 schema
    # and on a fresh install where v009 imports the current model metadata.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(40) NOT NULL DEFAULT 'participant'")
    additions = [
        "registration_id UUID REFERENCES registrations(id) ON DELETE CASCADE",
        "representative VARCHAR(255)", "contact_email VARCHAR(255)", "contact_phone VARCHAR(60)",
        "products TEXT", "services TEXT", "hs_code VARCHAR(100)", "production_capacity TEXT",
        "certificates TEXT", "markets_served TEXT", "preferred_slot_ids JSON NOT NULL DEFAULT '[]'",
        "estimated_deal_investment_value VARCHAR(255)", "additional_notes TEXT",
        "profile_sharing_consent BOOLEAN NOT NULL DEFAULT false", "profile_sharing_consent_at TIMESTAMPTZ",
    ]
    for definition in additions:
        op.execute(f"ALTER TABLE business_matching_profiles ADD COLUMN IF NOT EXISTS {definition}")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_business_matching_profiles_registration_id ON business_matching_profiles (registration_id)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_business_matching_profiles_registration_id")
    for name in ["profile_sharing_consent_at", "profile_sharing_consent", "additional_notes", "estimated_deal_investment_value", "preferred_slot_ids", "markets_served", "certificates", "production_capacity", "hs_code", "services", "products", "contact_phone", "contact_email", "representative", "registration_id"]:
        op.execute(f"ALTER TABLE business_matching_profiles DROP COLUMN IF EXISTS {name}")
    for table in reversed(TABLES): table.drop(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")
