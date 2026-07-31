import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.speakers.models import Speaker


class SpeakerRepository:
    @staticmethod
    async def list_speakers(session: AsyncSession, skip: int = 0, limit: int = 100):
        stmt = select(Speaker).order_by(Speaker.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_featured(session: AsyncSession, limit: int = 100):
        stmt = select(Speaker).where(Speaker.is_featured == True).order_by(Speaker.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, speaker_id: uuid.UUID) -> Speaker:
        speaker = await session.get(Speaker, speaker_id)
        if not speaker:
            raise NotFoundException(code="SPEAKER_NOT_FOUND", message="Speaker tidak ditemukan")
        return speaker

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> Speaker:
        speaker = Speaker(**data)
        session.add(speaker)
        await session.commit()
        await session.refresh(speaker)
        return speaker

    @staticmethod
    async def update(session: AsyncSession, speaker: Speaker, data: dict) -> Speaker:
        for key, value in data.items():
            if value is not None:
                setattr(speaker, key, value)
        await session.commit()
        await session.refresh(speaker)
        return speaker
