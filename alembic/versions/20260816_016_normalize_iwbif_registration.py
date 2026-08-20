"""normalize IWBIF registration ownership and selections

Revision ID: 202608160016
Revises: 202608160015
Create Date: 2026-08-16
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.modules.iwbif.models import (
    AccommodationTravel,
    BusinessMatchingProfileSlot,
    Company,
    RegistrationActivity,
    RegistrationParticipationCategory,
)


revision = "202608160016"
down_revision = "202608160015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        Company.__table__,
        AccommodationTravel.__table__,
        RegistrationParticipationCategory.__table__,
        RegistrationActivity.__table__,
        BusinessMatchingProfileSlot.__table__,
    ):
        table.create(bind, checkfirst=True)

    op.execute("ALTER TABLE delegate_registration_details ADD COLUMN IF NOT EXISTS company_id UUID")
    op.execute("ALTER TABLE exhibitor_registrations ADD COLUMN IF NOT EXISTS company_id UUID")
    op.execute("ALTER TABLE business_matching_profiles ADD COLUMN IF NOT EXISTS company_id UUID")
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_delegate_detail_company') THEN
            ALTER TABLE delegate_registration_details ADD CONSTRAINT fk_delegate_detail_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_exhibitor_company') THEN
            ALTER TABLE exhibitor_registrations ADD CONSTRAINT fk_exhibitor_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_business_profile_company') THEN
            ALTER TABLE business_matching_profiles ADD CONSTRAINT fk_business_profile_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_participants_user') THEN
            ALTER TABLE participants ADD CONSTRAINT fk_participants_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_exhibitor_event_participant') THEN
            ALTER TABLE exhibitor_registrations ADD CONSTRAINT uq_exhibitor_event_participant UNIQUE (event_id, participant_id);
          END IF;
        END $$;
    """)

    company_by_participant = {}
    delegates = bind.execute(sa.text("""
        SELECT r.participant_id, d.registration_id, d.company_organization,
               'Other' AS country,
               d.company_address, d.company_website, d.participation_categories,
               d.activity_ids, d.room_preference, d.preferred_roommate,
               d.arrival_date, d.departure_date, d.flight_number, d.airport,
               d.need_airport_pickup
        FROM delegate_registration_details d
        JOIN registrations r ON r.id = d.registration_id
    """)).mappings().all()
    for row in delegates:
        company_id = company_by_participant.get(row["participant_id"])
        if company_id is None:
            company_id = uuid.uuid4()
            company_by_participant[row["participant_id"]] = company_id
            bind.execute(Company.__table__.insert().values(
                id=company_id,
                participant_id=row["participant_id"],
                name=row["company_organization"],
                country=row["country"],
                address=row["company_address"],
                website=row["company_website"],
            ))
        bind.execute(sa.text("UPDATE delegate_registration_details SET company_id=:company_id WHERE registration_id=:registration_id"), {"company_id": company_id, "registration_id": row["registration_id"]})
        bind.execute(pg_insert(AccommodationTravel.__table__).values(
            registration_id=row["registration_id"], room_preference=row["room_preference"],
            preferred_roommate=row["preferred_roommate"], arrival_date=row["arrival_date"],
            departure_date=row["departure_date"], flight_number=row["flight_number"],
            airport=row["airport"], need_airport_pickup=row["need_airport_pickup"],
        ).on_conflict_do_nothing())
        for category in row["participation_categories"] or []:
            bind.execute(pg_insert(RegistrationParticipationCategory.__table__).values(registration_id=row["registration_id"], category=category).on_conflict_do_nothing())
        for activity_id in row["activity_ids"] or []:
            bind.execute(pg_insert(RegistrationActivity.__table__).values(registration_id=row["registration_id"], activity_id=uuid.UUID(str(activity_id))).on_conflict_do_nothing())

    for row in bind.execute(sa.text("SELECT id, participant_id, company_name, 'Other' AS country FROM exhibitor_registrations")).mappings():
        company_id = company_by_participant.get(row["participant_id"])
        if company_id is None:
            existing = bind.execute(sa.text("SELECT id FROM companies WHERE participant_id=:participant_id"), {"participant_id": row["participant_id"]}).scalar_one_or_none()
            company_id = existing or uuid.uuid4()
            company_by_participant[row["participant_id"]] = company_id
            if not existing:
                bind.execute(Company.__table__.insert().values(id=company_id, participant_id=row["participant_id"], name=row["company_name"], country=row["country"]))
        bind.execute(sa.text("UPDATE exhibitor_registrations SET company_id=:company_id WHERE id=:id"), {"company_id": company_id, "id": row["id"]})

    profiles = bind.execute(sa.text("SELECT id, participant_id, organization_name, country_code, preferred_slot_ids FROM business_matching_profiles")).mappings().all()
    for row in profiles:
        company_id = company_by_participant.get(row["participant_id"])
        if company_id is None:
            existing = bind.execute(sa.text("SELECT id FROM companies WHERE participant_id=:participant_id"), {"participant_id": row["participant_id"]}).scalar_one_or_none()
            company_id = existing or uuid.uuid4()
            company_by_participant[row["participant_id"]] = company_id
            if not existing:
                bind.execute(Company.__table__.insert().values(id=company_id, participant_id=row["participant_id"], name=row["organization_name"] or "Unnamed Company", country=row["country_code"] or "Other"))
        bind.execute(sa.text("UPDATE business_matching_profiles SET company_id=:company_id WHERE id=:id"), {"company_id": company_id, "id": row["id"]})
        for slot_id in row["preferred_slot_ids"] or []:
            bind.execute(pg_insert(BusinessMatchingProfileSlot.__table__).values(profile_id=row["id"], slot_id=uuid.UUID(str(slot_id))).on_conflict_do_nothing())


def downgrade() -> None:
    op.execute("ALTER TABLE business_matching_profiles DROP COLUMN IF EXISTS company_id")
    op.execute("ALTER TABLE exhibitor_registrations DROP COLUMN IF EXISTS company_id")
    op.execute("ALTER TABLE delegate_registration_details DROP COLUMN IF EXISTS company_id")
    for table in (
        BusinessMatchingProfileSlot.__table__, RegistrationActivity.__table__,
        RegistrationParticipationCategory.__table__, AccommodationTravel.__table__,
        Company.__table__,
    ):
        table.drop(op.get_bind(), checkfirst=True)
