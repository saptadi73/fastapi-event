from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.committee import schemas
from app.modules.committee.models import CommitteeMember
from app.modules.events.models import Event


class CommitteeService:
    @staticmethod
    async def list_for_event(db: AsyncSession, event_id: UUID, *, published_only: bool, page: int, size: int):
        filters = [CommitteeMember.event_id == event_id]
        if published_only:
            filters.append(CommitteeMember.status == "published")
        total = int((await db.execute(select(func.count(CommitteeMember.id)).where(*filters))).scalar_one())
        rows = (await db.execute(
            select(CommitteeMember).where(*filters)
            .order_by(CommitteeMember.display_order, CommitteeMember.created_at, CommitteeMember.id)
            .offset((page - 1) * size).limit(size)
        )).scalars().all()
        return list(rows), total

    @staticmethod
    async def get(db: AsyncSession, member_id: UUID) -> CommitteeMember:
        member = await db.get(CommitteeMember, member_id)
        if not member:
            raise NotFoundException("COMMITTEE_MEMBER_NOT_FOUND", "Committee member tidak ditemukan")
        return member

    @staticmethod
    async def create(db: AsyncSession, payload: schemas.CommitteeMemberCreate) -> CommitteeMember:
        if not await db.get(Event, payload.event_id):
            raise NotFoundException("EVENT_NOT_FOUND", "Event tidak ditemukan")
        member = CommitteeMember(**payload.model_dump())
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return member

    @staticmethod
    async def update(db: AsyncSession, member_id: UUID, payload: schemas.CommitteeMemberUpdate) -> CommitteeMember:
        member = await CommitteeService.get(db, member_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(member, field, value)
        await db.commit()
        await db.refresh(member)
        return member

    @staticmethod
    async def delete(db: AsyncSession, member_id: UUID) -> CommitteeMember:
        member = await CommitteeService.get(db, member_id)
        await db.delete(member)
        await db.commit()
        return member
