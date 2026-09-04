import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_admin
from app.core.i18n import request_locale
from app.modules.committee import schemas
from app.modules.committee.service import CommitteeService
from app.modules.content_translations.service import localize_models
from app.support.responses import success_response


public_router = APIRouter(prefix="/events", tags=["committee"])
admin_router = APIRouter(prefix="/admin/committee", tags=["admin-committee"])
logger = logging.getLogger(__name__)


@public_router.get("/{event_id}/committee", summary="List published event committee members")
async def list_public_committee(event_id: UUID, request: Request, page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=200), db: AsyncSession = Depends(get_db_session)):
    rows, total = await CommitteeService.list_for_event(db, event_id, published_only=True, page=page, size=size)
    data = await localize_models(db, "committee_member", rows, request_locale(request))
    pages = (total + size - 1) // size if total else 0
    return success_response("Committee event ditemukan", data=data, meta={"page": page, "size": size, "total": total, "pages": pages}, request=request)


@admin_router.get("", summary="List committee members for admin")
async def list_admin_committee(request: Request, event_id: UUID, page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=200), db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    rows, total = await CommitteeService.list_for_event(db, event_id, published_only=False, page=page, size=size)
    data = await localize_models(db, "committee_member", rows, request_locale(request))
    pages = (total + size - 1) // size if total else 0
    return success_response("Committee admin ditemukan", data=data, meta={"page": page, "size": size, "total": total, "pages": pages}, request=request)


@admin_router.post("", summary="Create committee member")
async def create_committee_member(payload: schemas.CommitteeMemberCreate, request: Request, db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    member = await CommitteeService.create(db, payload)
    return success_response("Committee member berhasil dibuat", schemas.CommitteeMemberRead.model_validate(member), request=request)


@admin_router.put("/{member_id}", summary="Update committee member")
async def update_committee_member(member_id: UUID, payload: schemas.CommitteeMemberUpdate, request: Request, db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    member = await CommitteeService.update(db, member_id, payload)
    return success_response("Committee member berhasil diubah", schemas.CommitteeMemberRead.model_validate(member), request=request)


@admin_router.post("/{member_id}/photo", summary="Upload committee member photo")
async def upload_committee_photo(member_id: UUID, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    from app.core.uploads import delete_uploaded_file, save_profile_photo

    current = await CommitteeService.get(db, member_id)
    old_photo = current.profile_photo_url
    photo_url = await save_profile_photo(file, "committee")
    try:
        member = await CommitteeService.update(db, member_id, schemas.CommitteeMemberUpdate(profile_photo_url=photo_url))
    except Exception:
        logger.exception("Committee photo database update failed: member_id=%s", member_id)
        delete_uploaded_file(photo_url)
        raise
    if old_photo and old_photo != photo_url:
        delete_uploaded_file(old_photo)
    return success_response("Foto committee berhasil diunggah", schemas.CommitteeMemberRead.model_validate(member), request=request)


@admin_router.delete("/{member_id}", summary="Delete committee member")
async def delete_committee_member(member_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session), admin=Depends(require_admin)):
    from app.core.uploads import delete_uploaded_file

    member = await CommitteeService.delete(db, member_id)
    if member.profile_photo_url:
        delete_uploaded_file(member.profile_photo_url)
    return success_response("Committee member berhasil dihapus", {"id": member_id}, request=request)
