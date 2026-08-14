from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user, get_db_session, require_admin
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.business_matching.models import BusinessMatchingProfile
from app.modules.participants.models import ParticipantProfile
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.users.models import User
from app.support.responses import success_response
from . import schemas
from .constants import *
from .models import BusinessMatchingSlot, DelegatePackage, DelegateRegistrationDetail, EventActivity, ExhibitorRegistration, RegistrationDocument
from .service import IwbifService

router = APIRouter()

@router.get("/master/business-sectors")
async def sectors(request: Request): return success_response("Master business sectors", BUSINESS_SECTORS, request=request)

@router.get("/master/countries")
async def countries(request: Request): return success_response("Master countries", COUNTRIES, request=request)

@router.get("/master/iwbif-options")
async def options(request: Request):
    return success_response("Master IWBIF options", {"participation_categories": PARTICIPATION_CATEGORIES, "looking_for": LOOKING_FOR, "preferred_countries": PREFERRED_COUNTRIES, "room_preferences": ROOM_PREFERENCES, "airports": AIRPORTS, "payment_methods": PAYMENT_METHODS, "booth_sizes": BOOTH_SIZES}, request=request)

@router.get("/events/{event_id}/delegate-packages")
async def packages(event_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session)):
    rows = list((await db.execute(select(DelegatePackage).where(DelegatePackage.event_id == event_id, DelegatePackage.is_active.is_(True)).order_by(DelegatePackage.amount))).scalars()); return success_response("Paket delegate ditemukan", [schemas.PackageRead.model_validate(x) for x in rows], request=request)

@router.get("/events/{event_id}/activities")
async def activities(event_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session)):
    rows = list((await db.execute(select(EventActivity).where(EventActivity.event_id == event_id, EventActivity.is_active.is_(True)).order_by(EventActivity.name))).scalars()); return success_response("Aktivitas ditemukan", [schemas.ActivityRead.model_validate(x) for x in rows], request=request)

@router.get("/events/{event_id}/business-matching-slots")
async def matching_slots(event_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session)):
    rows = list((await db.execute(select(BusinessMatchingSlot).where(BusinessMatchingSlot.event_id == event_id, BusinessMatchingSlot.is_active.is_(True)).order_by(BusinessMatchingSlot.slot_date, BusinessMatchingSlot.start_time))).scalars()); return success_response("Slot business matching ditemukan", [schemas.SlotRead.model_validate(x) for x in rows], request=request)

def master_crud(model, write_schema, read_schema, label):
    async def create(event_id: UUID, payload, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
        row = model(event_id=event_id, **payload.model_dump()); db.add(row); await db.commit(); await db.refresh(row); return success_response(f"{label} berhasil dibuat", read_schema.model_validate(row), request=request)
    async def get(event_id: UUID, item_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session)):
        row = await db.get(model, item_id)
        if not row or row.event_id != event_id: raise NotFoundException("MASTER_NOT_FOUND", f"{label} tidak ditemukan")
        return success_response(f"{label} ditemukan", read_schema.model_validate(row), request=request)
    async def update(event_id: UUID, item_id: UUID, payload, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
        row = await db.get(model, item_id, with_for_update=True)
        if not row or row.event_id != event_id: raise NotFoundException("MASTER_NOT_FOUND", f"{label} tidak ditemukan")
        for key, value in payload.model_dump().items(): setattr(row, key, value)
        await db.commit(); await db.refresh(row); return success_response(f"{label} berhasil diperbarui", read_schema.model_validate(row), request=request)
    async def delete(event_id: UUID, item_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
        row = await db.get(model, item_id, with_for_update=True)
        if not row or row.event_id != event_id: raise NotFoundException("MASTER_NOT_FOUND", f"{label} tidak ditemukan")
        await db.delete(row); await db.commit(); return success_response(f"{label} berhasil dihapus", request=request)
    return create, get, update, delete

for _model, _write, _read, _segment, _label in [
    (DelegatePackage, schemas.PackageWrite, schemas.PackageRead, "delegate-packages", "Paket delegate"),
    (EventActivity, schemas.ActivityWrite, schemas.ActivityRead, "activities", "Aktivitas"),
    (BusinessMatchingSlot, schemas.SlotWrite, schemas.SlotRead, "business-matching-slots", "Slot business matching"),
]:
    _create, _get, _update, _delete = master_crud(_model, _write, _read, _label)
    _create.__annotations__["payload"] = _write
    _update.__annotations__["payload"] = _write
    _create.__name__ = f"create_{_segment.replace('-', '_')}"
    _get.__name__ = f"get_{_segment.replace('-', '_')}"
    _update.__name__ = f"update_{_segment.replace('-', '_')}"
    _delete.__name__ = f"delete_{_segment.replace('-', '_')}"
    router.add_api_route(f"/admin/events/{{event_id}}/{_segment}", _create, methods=["POST"], response_model=None)
    router.add_api_route(f"/admin/events/{{event_id}}/{_segment}/{{item_id}}", _get, methods=["GET"], response_model=None)
    router.add_api_route(f"/admin/events/{{event_id}}/{_segment}/{{item_id}}", _update, methods=["PUT"], response_model=None)
    router.add_api_route(f"/admin/events/{{event_id}}/{_segment}/{{item_id}}", _delete, methods=["DELETE"], response_model=None)

@router.post("/events/{event_id}/registrations", status_code=201)
async def create_registration(event_id: UUID, payload: schemas.DelegateRegistrationWrite, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.create_registration(db, event_id, user.id, payload); return success_response("Draft registrasi IWBIF berhasil dibuat", await IwbifService.read_registration(db, reg.id, user.id), request=request)

@router.get("/events/{event_id}/registrations/{registration_id}")
async def registration(event_id: UUID, registration_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    data = await IwbifService.read_registration(db, registration_id, user.id)
    if data["event_id"] != event_id: raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
    return success_response("Registrasi IWBIF ditemukan", data, request=request)

@router.patch("/events/{event_id}/registrations/{registration_id}")
async def update_registration(event_id: UUID, registration_id: UUID, payload: schemas.DelegateRegistrationWrite, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.update_registration(db, registration_id, user.id, payload)
    if reg.event_id != event_id: raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
    return success_response("Draft registrasi berhasil diperbarui", await IwbifService.read_registration(db, reg.id, user.id), request=request)

@router.post("/events/{event_id}/registrations/{registration_id}/submit")
async def submit(event_id: UUID, registration_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.submit(db, registration_id, user.id)
    if reg.event_id != event_id: raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
    return success_response("Registrasi berhasil dikirim untuk verifikasi", {"id": reg.id, "status": reg.status}, request=request)

@router.delete("/events/{event_id}/registrations/{registration_id}")
async def cancel_registration(event_id: UUID, registration_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.owned_registration(db, registration_id, user.id)
    if reg.event_id != event_id: raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
    if reg.status == RegistrationStatus.CONFIRMED: raise ConflictException("REGISTRATION_NOT_CANCELLABLE", "Registrasi confirmed harus dibatalkan organizer")
    reg.status = RegistrationStatus.CANCELLED; reg.canceled_at = datetime.now(timezone.utc); await db.commit(); return success_response("Registrasi berhasil dibatalkan", request=request)

@router.post("/registrations/{registration_id}/documents", status_code=201)
async def upload_document(registration_id: UUID, request: Request, document_type: str = Form(...), file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await IwbifService.save_document(db, registration_id, user.id, document_type, file); return success_response("Dokumen berhasil diunggah", {"id": row.id, "document_type": row.document_type, "filename": row.original_filename, "mime_type": row.mime_type, "file_size": row.file_size}, request=request)

@router.get("/registrations/{registration_id}/documents")
async def documents(registration_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await IwbifService.owned_registration(db, registration_id, user.id); rows = list((await db.execute(select(RegistrationDocument).where(RegistrationDocument.registration_id == registration_id))).scalars()); data = [{"id": x.id, "document_type": x.document_type, "filename": x.original_filename, "mime_type": x.mime_type, "file_size": x.file_size, "uploaded_at": x.uploaded_at} for x in rows]; return success_response("Dokumen registrasi ditemukan", data, request=request)

@router.delete("/registrations/{registration_id}/documents/{document_id}")
async def delete_document(registration_id: UUID, document_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.owned_registration(db, registration_id, user.id)
    if reg.status != RegistrationStatus.DRAFT: raise ConflictException("REGISTRATION_NOT_EDITABLE", "Dokumen hanya dapat dihapus saat registrasi masih draft")
    row = (await db.execute(select(RegistrationDocument).where(RegistrationDocument.id == document_id, RegistrationDocument.registration_id == registration_id))).scalar_one_or_none()
    if not row: raise NotFoundException("DOCUMENT_NOT_FOUND", "Dokumen tidak ditemukan")
    path = Path(".private_uploads").resolve() / row.storage_key; await db.delete(row); await db.commit()
    if path.is_file(): path.unlink()
    return success_response("Dokumen berhasil dihapus", request=request)

@router.get("/registrations/{registration_id}/documents/{document_id}/download")
async def download_document(registration_id: UUID, document_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    await IwbifService.owned_registration(db, registration_id, user.id); row = (await db.execute(select(RegistrationDocument).where(RegistrationDocument.id == document_id, RegistrationDocument.registration_id == registration_id))).scalar_one_or_none()
    if not row: raise NotFoundException("DOCUMENT_NOT_FOUND", "Dokumen tidak ditemukan")
    path = Path(".private_uploads").resolve() / row.storage_key
    if not path.is_file(): raise NotFoundException("DOCUMENT_FILE_NOT_FOUND", "File dokumen tidak ditemukan")
    return FileResponse(path, media_type=row.mime_type, filename=row.original_filename)

@router.post("/events/{event_id}/exhibitors", status_code=201)
async def create_exhibitor(event_id: UUID, payload: schemas.ExhibitorWrite, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    return success_response("Draft exhibitor berhasil dibuat; unggah PRODUCT_CATALOGUE untuk melengkapi", schemas.ExhibitorRead.model_validate(await IwbifService.create_exhibitor(db, event_id, user.id, payload)), request=request)

@router.get("/events/{event_id}/exhibitors")
async def exhibitors(event_id: UUID, request: Request, db: AsyncSession = Depends(get_db_session)):
    rows = list((await db.execute(select(ExhibitorRegistration).where(ExhibitorRegistration.event_id == event_id, ExhibitorRegistration.status == "submitted").order_by(ExhibitorRegistration.company_name))).scalars()); return success_response("Daftar exhibitor ditemukan", [schemas.ExhibitorRead.model_validate(x) for x in rows], request=request)

@router.get("/events/{event_id}/exhibitors/{exhibitor_id}")
async def exhibitor(event_id: UUID, exhibitor_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(ExhibitorRegistration, exhibitor_id); participant = await db.get(ParticipantProfile, row.participant_id) if row else None
    if not row or row.event_id != event_id or not participant or participant.user_id != user.id: raise NotFoundException("EXHIBITOR_NOT_FOUND", "Exhibitor tidak ditemukan")
    return success_response("Exhibitor ditemukan", schemas.ExhibitorRead.model_validate(row), request=request)

@router.put("/events/{event_id}/exhibitors/{exhibitor_id}")
async def update_exhibitor(event_id: UUID, exhibitor_id: UUID, payload: schemas.ExhibitorWrite, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(ExhibitorRegistration, exhibitor_id, with_for_update=True); participant = await db.get(ParticipantProfile, row.participant_id) if row else None
    if not row or row.event_id != event_id or not participant or participant.user_id != user.id: raise NotFoundException("EXHIBITOR_NOT_FOUND", "Exhibitor tidak ditemukan")
    if row.status != "draft": raise ConflictException("EXHIBITOR_NOT_EDITABLE", "Hanya draft exhibitor yang dapat diubah")
    if payload.participant_id != row.participant_id: raise ValidationException("PARTICIPANT_IMMUTABLE", "Participant tidak dapat diubah")
    data = payload.model_dump(exclude={"participant_id"}); data["email"] = str(data["email"])
    for key, value in data.items(): setattr(row, key, value)
    row.exhibition_terms_accepted_at = datetime.now(timezone.utc); await db.commit(); await db.refresh(row); return success_response("Exhibitor berhasil diperbarui", schemas.ExhibitorRead.model_validate(row), request=request)

@router.delete("/events/{event_id}/exhibitors/{exhibitor_id}")
async def delete_exhibitor(event_id: UUID, exhibitor_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await db.get(ExhibitorRegistration, exhibitor_id, with_for_update=True); participant = await db.get(ParticipantProfile, row.participant_id) if row else None
    if not row or row.event_id != event_id or not participant or participant.user_id != user.id: raise NotFoundException("EXHIBITOR_NOT_FOUND", "Exhibitor tidak ditemukan")
    if row.status != "draft": raise ConflictException("EXHIBITOR_NOT_DELETABLE", "Hanya draft exhibitor yang dapat dihapus")
    await db.delete(row); await db.commit(); return success_response("Exhibitor berhasil dihapus", request=request)

@router.post("/exhibitors/{exhibitor_id}/product-catalogue", status_code=201)
async def exhibitor_catalogue(exhibitor_id: UUID, request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    row = await IwbifService.save_exhibitor_catalogue(db, exhibitor_id, user.id, file); return success_response("Katalog produk berhasil diunggah dan exhibitor dikirim", {"id": row.id, "document_type": row.document_type}, request=request)

@router.post("/registrations/{registration_id}/business-matching-profile", status_code=201)
@router.patch("/registrations/{registration_id}/business-matching-profile")
async def matching_profile(registration_id: UUID, payload: schemas.MatchingProfileWrite, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.owned_registration(db, registration_id, user.id)
    if reg.status != RegistrationStatus.CONFIRMED: raise HTTPException(403, "Business matching profile is available to confirmed delegates only")
    slots = set((await db.execute(select(BusinessMatchingSlot.id).where(BusinessMatchingSlot.event_id == reg.event_id, BusinessMatchingSlot.is_active.is_(True), BusinessMatchingSlot.id.in_(payload.preferred_slot_ids)))).scalars())
    if slots != set(payload.preferred_slot_ids): raise ValidationException("INVALID_MATCHING_SLOT", "Slot business matching tidak valid")
    row = (await db.execute(select(BusinessMatchingProfile).where(BusinessMatchingProfile.registration_id == reg.id))).scalar_one_or_none()
    if not row: row = BusinessMatchingProfile(event_id=reg.event_id, participant_id=reg.participant_id, registration_id=reg.id); db.add(row)
    data = payload.model_dump(); row.organization_name = data.pop("company_name"); row.contact_email = str(data.pop("email")); row.business_needs = data.pop("looking_for"); row.preferred_regions = data.pop("preferred_countries"); row.preferred_slot_ids = [str(x) for x in data.pop("preferred_slot_ids")]
    for key, value in data.items(): setattr(row, key, value)
    row.available_for_matching = True; row.profile_sharing_consent_at = datetime.now(timezone.utc); await db.commit(); await db.refresh(row)
    return success_response("Business matching profile berhasil disimpan", {"id": row.id, "registration_id": row.registration_id}, request=request)

@router.get("/registrations/{registration_id}/business-matching-profile")
async def get_matching_profile(registration_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.owned_registration(db, registration_id, user.id); row = (await db.execute(select(BusinessMatchingProfile).where(BusinessMatchingProfile.registration_id == reg.id))).scalar_one_or_none()
    if not row: raise NotFoundException("BUSINESS_PROFILE_NOT_FOUND", "Profil business matching tidak ditemukan")
    return success_response("Business matching profile ditemukan", {c.name: getattr(row, c.name) for c in row.__table__.columns}, request=request)

@router.delete("/registrations/{registration_id}/business-matching-profile")
async def delete_matching_profile(registration_id: UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    reg = await IwbifService.owned_registration(db, registration_id, user.id); row = (await db.execute(select(BusinessMatchingProfile).where(BusinessMatchingProfile.registration_id == reg.id))).scalar_one_or_none()
    if not row: raise NotFoundException("BUSINESS_PROFILE_NOT_FOUND", "Profil business matching tidak ditemukan")
    await db.delete(row); await db.commit(); return success_response("Business matching profile berhasil dihapus", request=request)

@router.get("/admin/events/{event_id}/registrations")
async def admin_registrations(event_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    rows = list((await db.execute(select(Registration).where(Registration.event_id == event_id).order_by(Registration.registration_number))).scalars()); return success_response("Registrasi admin ditemukan", [{"id": x.id, "registration_number": x.registration_number, "status": x.status, "participant_id": x.participant_id} for x in rows], request=request)

def admin_command(target_status):
    async def endpoint(registration_id: UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
        row = await db.get(Registration, registration_id, with_for_update=True)
        if not row: raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
        allowed = {RegistrationStatus.UNDER_VERIFICATION: {RegistrationStatus.SUBMITTED}, RegistrationStatus.VERIFIED: {RegistrationStatus.UNDER_VERIFICATION, RegistrationStatus.SUBMITTED}, RegistrationStatus.CONFIRMED: {RegistrationStatus.VERIFIED, RegistrationStatus.PAID}, RegistrationStatus.REJECTED: {RegistrationStatus.SUBMITTED, RegistrationStatus.UNDER_VERIFICATION, RegistrationStatus.VERIFIED}}
        if row.status not in allowed[target_status]: raise ConflictException("INVALID_REGISTRATION_TRANSITION", "Transisi registrasi tidak valid")
        row.status = target_status
        if target_status == RegistrationStatus.CONFIRMED: row.confirmed_at = datetime.now(timezone.utc)
        await db.commit(); return success_response("Status registrasi berhasil diubah", {"id": row.id, "status": row.status}, request=request)
    return endpoint

router.add_api_route("/admin/registrations/{registration_id}/verify", admin_command(RegistrationStatus.VERIFIED), methods=["POST"])
router.add_api_route("/admin/registrations/{registration_id}/confirm", admin_command(RegistrationStatus.CONFIRMED), methods=["POST"])
router.add_api_route("/admin/registrations/{registration_id}/reject", admin_command(RegistrationStatus.REJECTED), methods=["POST"])
