import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.workshop_tracks.models import WorkshopTrack


class WorkshopTrackRepository:
    @staticmethod
    async def list_by_event(session: AsyncSession, event_id: uuid.UUID):
        stmt = select(WorkshopTrack).where(WorkshopTrack.event_id == event_id).order_by(WorkshopTrack.order_index.asc())
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get(session: AsyncSession, track_id: uuid.UUID) -> WorkshopTrack:
        obj = await session.get(WorkshopTrack, track_id)
        if not obj:
            raise NotFoundException(code="WORKSHOP_TRACK_NOT_FOUND", message="Workshop track tidak ditemukan")
        return obj

    @staticmethod
    async def create(session: AsyncSession, payload: dict) -> WorkshopTrack:
        obj = WorkshopTrack(**payload)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @staticmethod
    async def update(session: AsyncSession, obj: WorkshopTrack, payload: dict) -> WorkshopTrack:
        for key, value in payload.items():
            if value is not None:
                setattr(obj, key, value)
        await session.commit()
        await session.refresh(obj)
        return obj

