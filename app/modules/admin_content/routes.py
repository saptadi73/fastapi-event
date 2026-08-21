from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session, require_admin
from app.core.exceptions import NotFoundException
from app.modules.admin_content import schemas
from app.modules.admin_content.models import Announcement, Certificate
from app.modules.users.models import User
from app.support.responses import success_response

router = APIRouter(tags=["admin-content"])


@router.get("/events/{event_id}/announcements")
async def list_announcements(event_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Announcement).where(Announcement.event_id == event_id, Announcement.status == "published").order_by(Announcement.published_at.desc()))).scalars().all()
    return success_response("Announcement ditemukan", [schemas.AnnouncementRead.model_validate(row) for row in rows], request=request)


@router.get("/admin/events/{event_id}/announcements")
async def admin_announcements(event_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Announcement).where(Announcement.event_id == event_id).order_by(Announcement.created_at.desc()))).scalars().all()
    return success_response("Announcement admin ditemukan", [schemas.AnnouncementRead.model_validate(row) for row in rows], request=request)


@router.post("/admin/events/{event_id}/announcements", status_code=201)
async def create_announcement(event_id: UUID, payload: schemas.AnnouncementWrite, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    data = payload.model_dump()
    if data["status"] == "published" and not data["published_at"]:
        data["published_at"] = datetime.now(timezone.utc)
    row = Announcement(event_id=event_id, **data); db.add(row); await db.commit(); await db.refresh(row)
    return success_response("Announcement berhasil dibuat", schemas.AnnouncementRead.model_validate(row), request=request)


@router.put("/admin/announcements/{item_id}")
async def update_announcement(item_id: UUID, payload: schemas.AnnouncementWrite, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(Announcement, item_id)
    if not row: raise NotFoundException("ANNOUNCEMENT_NOT_FOUND", "Announcement tidak ditemukan")
    data = payload.model_dump()
    if data["status"] == "published" and not data["published_at"]: data["published_at"] = datetime.now(timezone.utc)
    for key, value in data.items(): setattr(row, key, value)
    await db.commit(); await db.refresh(row)
    return success_response("Announcement berhasil diperbarui", schemas.AnnouncementRead.model_validate(row), request=request)


@router.delete("/admin/announcements/{item_id}")
async def delete_announcement(item_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(Announcement, item_id)
    if not row: raise NotFoundException("ANNOUNCEMENT_NOT_FOUND", "Announcement tidak ditemukan")
    await db.delete(row); await db.commit()
    return success_response("Announcement berhasil dihapus", {"id": item_id}, request=request)


@router.get("/certificates/me")
async def my_certificates(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Certificate).where(Certificate.user_id == user.id).order_by(Certificate.issued_at.desc()))).scalars().all()
    return success_response("Certificate ditemukan", [schemas.CertificateRead.model_validate(row) for row in rows], request=request)


@router.get("/admin/events/{event_id}/certificates")
async def admin_certificates(event_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(Certificate).where(Certificate.event_id == event_id).order_by(Certificate.issued_at.desc()))).scalars().all()
    return success_response("Certificate admin ditemukan", [schemas.CertificateRead.model_validate(row) for row in rows], request=request)


@router.post("/admin/certificates", status_code=201)
async def create_certificate(payload: schemas.CertificateWrite, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    data = payload.model_dump(exclude_none=True); row = Certificate(**data); db.add(row); await db.commit(); await db.refresh(row)
    return success_response("Certificate berhasil diterbitkan", schemas.CertificateRead.model_validate(row), request=request)


@router.put("/admin/certificates/{item_id}")
async def update_certificate(item_id: UUID, payload: schemas.CertificateWrite, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(Certificate, item_id)
    if not row: raise NotFoundException("CERTIFICATE_NOT_FOUND", "Certificate tidak ditemukan")
    for key, value in payload.model_dump(exclude_none=True).items(): setattr(row, key, value)
    await db.commit(); await db.refresh(row)
    return success_response("Certificate berhasil diperbarui", schemas.CertificateRead.model_validate(row), request=request)


@router.delete("/admin/certificates/{item_id}")
async def delete_certificate(item_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(Certificate, item_id)
    if not row: raise NotFoundException("CERTIFICATE_NOT_FOUND", "Certificate tidak ditemukan")
    await db.delete(row); await db.commit()
    return success_response("Certificate berhasil dihapus", {"id": item_id}, request=request)
