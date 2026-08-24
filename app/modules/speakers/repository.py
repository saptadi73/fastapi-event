import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.speakers.models import EventSpeaker, Speaker


class SpeakerRepository:
    @staticmethod
    async def list_speakers(session: AsyncSession, skip: int = 0, limit: int = 100):
        stmt = select(Speaker).order_by(Speaker.created_at.asc()).offset(skip).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_featured(session: AsyncSession, limit: int = 100):
        stmt = select(Speaker).where(Speaker.is_featured == True).order_by(Speaker.created_at.asc()).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_featured_by_event(session: AsyncSession, event_id: uuid.UUID, limit: int = 100):
        stmt = (select(Speaker).join(EventSpeaker, EventSpeaker.speaker_id == Speaker.id)
                .where(EventSpeaker.event_id == event_id, Speaker.is_featured.is_(True))
                .order_by(Speaker.created_at.asc()).limit(limit))
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

    @staticmethod
    async def delete(session: AsyncSession, speaker: Speaker) -> None:
        await session.delete(speaker)
        await session.commit()

    @staticmethod
    async def assign_event(session: AsyncSession, speaker_id: uuid.UUID, event_id: uuid.UUID) -> None:
        existing = await session.get(EventSpeaker, {"event_id": event_id, "speaker_id": speaker_id})
        if not existing:
            session.add(EventSpeaker(event_id=event_id, speaker_id=speaker_id))
            await session.commit()

    @staticmethod
    async def remove_event(session: AsyncSession, speaker_id: uuid.UUID, event_id: uuid.UUID) -> bool:
        result = await session.execute(delete(EventSpeaker).where(
            EventSpeaker.event_id == event_id,
            EventSpeaker.speaker_id == speaker_id,
        ))
        await session.commit()
        return bool(result.rowcount)
