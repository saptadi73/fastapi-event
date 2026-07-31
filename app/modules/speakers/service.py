from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.speakers import schemas
from app.modules.speakers.repository import SpeakerRepository


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
