from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.participants.models import ParticipantProfile


class ParticipantRepository:
    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: UUID) -> ParticipantProfile | None:
        stmt = select(ParticipantProfile).where(ParticipantProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, profile_id: UUID) -> ParticipantProfile:
        profile = await session.get(ParticipantProfile, profile_id)
        if not profile:
            raise NotFoundException(code="PARTICIPANT_PROFILE_NOT_FOUND", message="Profile participant tidak ditemukan")
        return profile

    @staticmethod
    async def create(session: AsyncSession, *, user_id: UUID, full_name: str, organization_name: str | None, biography: str | None) -> ParticipantProfile:
        existing = await ParticipantRepository.get_by_user_id(session, user_id)
        if existing:
            raise ConflictException(code="PARTICIPANT_PROFILE_EXISTS", message="Profile untuk user ini sudah ada")

        profile = ParticipantProfile(
            user_id=user_id,
            full_name=full_name,
            organization_name=organization_name,
            biography=biography,
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile

    @staticmethod
    async def update(session: AsyncSession, user_id: UUID, payload: dict) -> ParticipantProfile:
        profile = await ParticipantRepository.get_by_user_id(session, user_id)
        if not profile:
            raise NotFoundException(code="PARTICIPANT_PROFILE_NOT_FOUND", message="Profile belum dibuat")
        for key, value in payload.items():
            if value is not None:
                setattr(profile, key, value)
        await session.commit()
        await session.refresh(profile)
        return profile

