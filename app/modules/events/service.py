from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.events import schemas
from app.modules.events.repository import EventRepository


class EventService:
    @staticmethod
    async def list_events(session: AsyncSession, page: int = 1, size: int = 20):
        skip = (page - 1) * size
        items, total = await EventRepository.list_events(session, skip=skip, limit=size)
        pages = max((total + size - 1) // size, 1)
        return items, {
            "page": page,
            "size": size,
            "total": total,
            "pages": pages,
        }

    @staticmethod
    async def get_by_id(session: AsyncSession, event_id: UUID) -> schemas.EventRead:
        event = await EventRepository.get_event_by_id(session, event_id)
        return schemas.EventRead.model_validate(event)

    @staticmethod
    async def get_by_slug(session: AsyncSession, slug: str):
        return await EventRepository.get_by_slug(session, slug)

    @staticmethod
    async def create(session: AsyncSession, payload: schemas.EventCreate):
        if payload.start_at >= payload.end_at:
            raise ValidationException(code="INVALID_TIME", message="start_at harus lebih awal dari end_at")
        return await EventRepository.create(session=session, **payload.dict())

    @staticmethod
    async def update(session: AsyncSession, event_id: UUID, payload: schemas.EventUpdate):
        event = await EventRepository.get_event_by_id(session, event_id)
        return await EventRepository.update(session=session, event=event, **payload.model_dump(exclude_unset=True))

