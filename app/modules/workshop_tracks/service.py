from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workshop_tracks import schemas
from app.modules.workshop_tracks.repository import WorkshopTrackRepository


class WorkshopTrackService:
    @staticmethod
    async def list_by_event(session: AsyncSession, event_id: UUID):
        rows = await WorkshopTrackRepository.list_by_event(session, event_id)
        return [schemas.WorkshopTrackRead.model_validate(row) for row in rows]

    @staticmethod
    async def get(session: AsyncSession, track_id: UUID):
        row = await WorkshopTrackRepository.get(session, track_id)
        return schemas.WorkshopTrackRead.model_validate(row)

    @staticmethod
    async def create(session: AsyncSession, payload: schemas.WorkshopTrackCreate):
        row = await WorkshopTrackRepository.create(session, payload.model_dump())
        return schemas.WorkshopTrackRead.model_validate(row)

    @staticmethod
    async def update(session: AsyncSession, track_id: UUID, payload: schemas.WorkshopTrackUpdate):
        row = await WorkshopTrackRepository.get(session, track_id)
        updated = await WorkshopTrackRepository.update(session, row, payload.model_dump(exclude_unset=True))
        return schemas.WorkshopTrackRead.model_validate(updated)

