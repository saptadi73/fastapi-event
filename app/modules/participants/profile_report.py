"""Combined participant dossier. Exposed only through the admin report router."""
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app.core.exceptions import NotFoundException
from app.modules.participants.models import ParticipantProfile
from app.modules.users.models import User
from app.modules.registrations.models import Registration
from app.modules.events.models import Event
from app.modules.business_matching.models import BusinessMatchingProfile
from app.modules.iwbif.models import (
    Company, DelegateRegistrationDetail, AccommodationTravel,
    DelegateRegistrationPackageSelection, RegistrationActivity, EventActivity,
    ExhibitorRegistration, RegistrationDocument, BusinessMatchingSlot,
)


def record(row, *, fields=None, exclude=()):
    if row is None:
        return None
    names = fields if fields is not None else [column.name for column in row.__table__.columns]
    return jsonable_encoder({name: getattr(row, name) for name in names if name not in exclude})


async def participant_profile_report(db, participant_id: UUID):
    profile = await db.get(ParticipantProfile, participant_id)
    if profile is None:
        raise NotFoundException('PARTICIPANT_PROFILE_NOT_FOUND', 'Profil peserta tidak ditemukan')
    user = await db.get(User, profile.user_id)
    # Explicit account allowlist: never serialize password hashes or auth tokens.
    account = record(user, fields=(
        'id', 'full_name', 'email', 'phone', 'country', 'role', 'status',
        'registration_status', 'preferred_locale', 'is_email_verified', 'created_at',
    ))

    async def rows(model, condition):
        statement = select(model).where(condition).order_by(*model.__table__.primary_key.columns)
        return list((await db.execute(statement)).scalars().all())

    async def event_info(event_id):
        event = await db.get(Event, event_id)
        return record(event, fields=('id', 'name', 'start_at', 'end_at'))

    async def documents(condition):
        return [record(row, exclude=('storage_key',)) for row in await rows(RegistrationDocument, condition)]

    registrations = []
    for registration in await rows(Registration, Registration.participant_id == participant_id):
        activities = list((await db.execute(
            select(EventActivity).join(RegistrationActivity, RegistrationActivity.activity_id == EventActivity.id)
            .where(RegistrationActivity.registration_id == registration.id).order_by(EventActivity.name)
        )).scalars().all())
        registrations.append({
            'registration': record(registration),
            'event': await event_info(registration.event_id),
            'delegate': record(await db.get(DelegateRegistrationDetail, registration.id)),
            'accommodation_travel': record(await db.get(AccommodationTravel, registration.id)),
            'packages': [record(row) for row in await rows(DelegateRegistrationPackageSelection, DelegateRegistrationPackageSelection.registration_id == registration.id)],
            'activities': [record(row) for row in activities],
            'documents': await documents(RegistrationDocument.registration_id == registration.id),
        })

    exhibitors = []
    for exhibitor in await rows(ExhibitorRegistration, ExhibitorRegistration.participant_id == participant_id):
        exhibitors.append({
            'exhibitor': record(exhibitor),
            'event': await event_info(exhibitor.event_id),
            'documents': await documents(RegistrationDocument.exhibitor_id == exhibitor.id),
        })

    matching = []
    for business in await rows(BusinessMatchingProfile, BusinessMatchingProfile.participant_id == participant_id):
        slot_ids = []
        for value in business.preferred_slot_ids or []:
            try:
                slot_ids.append(UUID(str(value)))
            except (ValueError, TypeError):
                continue
        matching.append({
            'business': record(business),
            'event': await event_info(business.event_id),
            'preferred_slots': [record(row) for row in await rows(BusinessMatchingSlot, BusinessMatchingSlot.id.in_(slot_ids))] if slot_ids else [],
        })
    return {
        'participant_id': str(profile.id),
        'account': account,
        'profile': record(profile),
        'companies': [record(row) for row in await rows(Company, Company.participant_id == participant_id)],
        'registrations': registrations,
        'exhibitors': exhibitors,
        'business_matching': matching,
    }
