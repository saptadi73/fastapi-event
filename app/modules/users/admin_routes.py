from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_admin
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.core.security import hash_password
from app.modules.users import schemas
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.support.responses import success_response

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def ensure_role_authority(actor: User, target_role: str, target: User | None = None) -> None:
    if actor.role == "organizer" and (target_role == "admin" or (target and target.role == "admin")):
        raise ValidationException("ROLE_NOT_ALLOWED", "Organizer tidak dapat membuat atau mengubah akun admin")


@router.get("")
async def list_users(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), role: str | None = None, status: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    filters = []
    if role: filters.append(User.role == role)
    if status: filters.append(User.status == status)
    stmt = select(User).where(*filters).order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()
    total = int((await db.scalar(select(func.count()).select_from(User).where(*filters))) or 0)
    return success_response("Daftar user ditemukan", [schemas.UserRead.model_validate(row) for row in rows], meta={"page": page, "size": size, "total": total, "pages": max((total + size - 1) // size, 1)}, request=request)


@router.post("", status_code=201)
async def create_user(payload: schemas.AdminUserCreate, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    ensure_role_authority(admin, payload.role)
    row = await UserRepository.create(
        db,
        payload.email,
        hash_password(payload.password),
        payload.country,
        payload.phone,
        payload.preferred_locale,
    )
    row.full_name = payload.full_name
    row.role = payload.role
    row.status = payload.status
    row.is_email_verified = payload.is_email_verified
    await db.commit(); await db.refresh(row)
    return success_response("User berhasil dibuat", schemas.UserRead.model_validate(row), request=request)


@router.put("/{user_id}")
async def update_user(user_id: UUID, payload: schemas.AdminUserUpdate, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(User, user_id)
    if not row: raise NotFoundException("USER_NOT_FOUND", "User tidak ditemukan")
    desired_role = payload.role or row.role
    ensure_role_authority(admin, desired_role, row)
    if row.id == admin.id and ((payload.role and payload.role != row.role) or (payload.status and payload.status != "active")):
        raise ConflictException("SELF_LOCKOUT", "Role atau status akun sendiri tidak dapat diubah")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None: setattr(row, key, value)
    await db.commit(); await db.refresh(row)
    return success_response("User berhasil diperbarui", schemas.UserRead.model_validate(row), request=request)
