from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.speakers import schemas
from app.modules.speakers.repository import SpeakerRepository
from app.core.exceptions import NotFoundException
from app.modules.events.models import Event


class SpeakerService:
    @staticmethod
    async def list(session: AsyncSession, page: int = 1, size: int = 20):
        skip = (page - 1) * size
        rows = await SpeakerRepository.list_speakers(session, skip=skip, limit=size)
        return rows

    @staticmethod
    async def list_featured(session: AsyncSession, size: int = 20):
        return await SpeakerRepository.list_featured(session, limit=size)

    @staticmethod
    async def list_featured_by_event(session: AsyncSession, event_id: UUID, size: int = 100):
        return await SpeakerRepository.list_featured_by_event(session, event_id, limit=size)

    @staticmethod
    async def get(session: AsyncSession, speaker_id: UUID):
        speaker = await SpeakerRepository.get_by_id(session, speaker_id)
        return schemas.SpeakerRead.model_validate(speaker)

    @staticmethod
    async def create(session: AsyncSession, payload: schemas.SpeakerCreate):
        data = payload.model_dump()
        speaker = await SpeakerRepository.create(session, data)
        return schemas.SpeakerRead.model_validate(speaker)

    @staticmethod
    async def update(session: AsyncSession, speaker_id: UUID, payload: schemas.SpeakerUpdate):
        speaker = await SpeakerRepository.get_by_id(session, speaker_id)
        payload_data = payload.model_dump(exclude_unset=True)
        updated = await SpeakerRepository.update(session, speaker, payload_data)
        return schemas.SpeakerRead.model_validate(updated)

    @staticmethod
    async def delete(session: AsyncSession, speaker_id: UUID) -> None:
        speaker = await SpeakerRepository.get_by_id(session, speaker_id)
        await SpeakerRepository.delete(session, speaker)

    @staticmethod
    async def assign_event(session: AsyncSession, speaker_id: UUID, event_id: UUID) -> None:
        await SpeakerRepository.get_by_id(session, speaker_id)
        if not await session.get(Event, event_id):
            raise NotFoundException(code="EVENT_NOT_FOUND", message="Event tidak ditemukan")
        await SpeakerRepository.assign_event(session, speaker_id, event_id)

    @staticmethod
    async def remove_event(session: AsyncSession, speaker_id: UUID, event_id: UUID) -> None:
        await SpeakerRepository.get_by_id(session, speaker_id)
        if not await SpeakerRepository.remove_event(session, speaker_id, event_id):
            raise NotFoundException(code="EVENT_SPEAKER_NOT_FOUND", message="Speaker tidak terhubung ke event")
