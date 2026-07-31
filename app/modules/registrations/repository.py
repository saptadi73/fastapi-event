from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.events.models import Event
from app.modules.registrations.models import Registration, RegistrationStatus


class RegistrationRepository:
    @staticmethod
    async def get_by_id(session: AsyncSession, registration_id: UUID) -> Registration:
        registration = await session.get(Registration, registration_id)
        if not registration:
            raise NotFoundException(code="REGISTRATION_NOT_FOUND", message="Registrasi tidak ditemukan")
        return registration

    @staticmethod
    async def get_by_event_participant(session: AsyncSession, event_id: UUID, participant_id: UUID) -> Registration | None:
        stmt = select(Registration).where(
            Registration.event_id == event_id,
            Registration.participant_id == participant_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, **kwargs) -> Registration:
        existing = await RegistrationRepository.get_by_event_participant(
            session=session,
            event_id=kwargs["event_id"],
            participant_id=kwargs["participant_id"],
        )
        if existing and existing.status != RegistrationStatus.CANCELED:
            raise ConflictException(code="REGISTRATION_EXISTS", message="Peserta sudah terdaftar di event ini")

        event = await session.get(Event, kwargs["event_id"])
        if not event:
            raise ValidationException(code="EVENT_NOT_FOUND", message="Event tidak ditemukan")

        registration = Registration(**kwargs)
        session.add(registration)
        await session.commit()
        await session.refresh(registration)
        return registration

