from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.events.models import Event, EventStatus


class EventRepository:
    @staticmethod
    async def list_events(session: AsyncSession, skip: int = 0, limit: int = 20):
        stmt = select(Event).order_by(Event.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        total = await session.scalar(select(func.count()).select_from(Event))
        return rows, int(total or 0)

    @staticmethod
    async def get_event_by_id(session: AsyncSession, event_id: UUID) -> Event:
        event = await session.get(Event, event_id)
        if not event:
            raise NotFoundException(code="EVENT_NOT_FOUND", message=f"Event {event_id} tidak ditemukan")
        return event

    @staticmethod
    async def get_by_slug(session: AsyncSession, slug: str) -> Event:
        stmt = select(Event).where(Event.slug == slug)
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()
        if not event:
            raise NotFoundException(code="EVENT_NOT_FOUND", message=f"Event slug={slug} tidak ditemukan")
        return event

    @staticmethod
    async def create(session: AsyncSession, *, name: str, slug: str, description: str | None, venue_name: str | None,
                     venue_address: str | None, timezone: str, start_at: datetime, end_at: datetime, capacity: int) -> Event:
        event = Event(
            name=name,
            slug=slug,
            description=description,
            venue_name=venue_name,
            venue_address=venue_address,
            timezone=timezone,
            start_at=start_at,
            end_at=end_at,
            capacity=capacity,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event

    @staticmethod
    async def update(session: AsyncSession, event: Event, **changes) -> Event:
        for key, value in changes.items():
            if value is not None and hasattr(event, key):
                setattr(event, key, value)
        if "status" in changes and isinstance(changes["status"], str):
            try:
                event.status = EventStatus(changes["status"])
            except ValueError:
                raise ValueError("status tidak valid")

        await session.commit()
        await session.refresh(event)
        return event

    @staticmethod
    async def delete(session: AsyncSession, event: Event) -> None:
        await session.delete(event)
        await session.commit()
