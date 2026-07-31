import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.modules.sessions.models import EventSession


class SessionRepository:
    @staticmethod
    async def list_by_event(session: AsyncSession, event_id: uuid.UUID):
        stmt = select(EventSession).where(EventSession.event_id == event_id).order_by(EventSession.start_at)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get(session: AsyncSession, session_id: uuid.UUID) -> EventSession:
        data = await session.get(EventSession, session_id)
        if not data:
            raise NotFoundException(code="SESSION_NOT_FOUND", message="Session tidak ditemukan")
        return data

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> EventSession:
        evt = EventSession(**data)
        session.add(evt)
        await session.commit()
        await session.refresh(evt)
        return evt

    @staticmethod
    async def update(session: AsyncSession, existing: EventSession, payload: dict) -> EventSession:
        for key, value in payload.items():
            if value is not None:
                setattr(existing, key, value)
        if "start_at" in payload and "end_at" in payload and payload["start_at"] and payload["end_at"]:
            if payload["start_at"] >= payload["end_at"]:
                raise ValidationException(code="INVALID_TIME", message="start_at harus lebih awal dari end_at")
        await session.commit()
        await session.refresh(existing)
        return existing

