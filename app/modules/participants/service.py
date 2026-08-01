from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.participants import schemas
from app.modules.participants.repository import ParticipantRepository


class ParticipantService:
    @staticmethod
    async def list(session: AsyncSession, page: int = 1, size: int = 20) -> list[schemas.ParticipantProfileRead]:
        rows = await ParticipantRepository.list_profiles(session, skip=(page - 1) * size, limit=size)
        return [schemas.ParticipantProfileRead.model_validate(row) for row in rows]

    @staticmethod
    async def get(session: AsyncSession, profile_id: UUID) -> schemas.ParticipantProfileRead:
        profile = await ParticipantRepository.get_by_id(session, profile_id)
        return schemas.ParticipantProfileRead.model_validate(profile)

    @staticmethod
    async def get_me(session: AsyncSession, user_id: UUID) -> schemas.ParticipantProfileRead | None:
        profile = await ParticipantRepository.get_by_user_id(session, user_id)
        if not profile:
            return None
        return schemas.ParticipantProfileRead.model_validate(profile)

    @staticmethod
    async def upsert_me(session: AsyncSession, user_id: UUID, payload: schemas.ParticipantProfileCreate) -> schemas.ParticipantProfileRead:
        existing = await ParticipantRepository.get_by_user_id(session, user_id)
        if existing:
            profile = await ParticipantRepository.update(
                session=session,
                user_id=user_id,
                payload=payload.model_dump(),
            )
        else:
            profile = await ParticipantRepository.create(
                session=session,
                user_id=user_id,
                full_name=payload.full_name,
                organization_name=payload.organization_name,
                biography=payload.biography,
                profile_photo_url=payload.profile_photo_url,
            )
        return schemas.ParticipantProfileRead.model_validate(profile)

    @staticmethod
    async def update_me(session: AsyncSession, user_id: UUID, payload: schemas.ParticipantProfileUpdate) -> schemas.ParticipantProfileRead:
        profile = await ParticipantRepository.update(
            session=session,
            user_id=user_id,
            payload=payload.model_dump(exclude_unset=True),
        )
        return schemas.ParticipantProfileRead.model_validate(profile)
