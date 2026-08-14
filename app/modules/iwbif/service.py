import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.events.models import Event
from app.modules.participants.models import ParticipantProfile
from app.modules.registrations.models import Registration, RegistrationStatus
from .models import BusinessMatchingSlot, DelegatePackage, DelegateRegistrationDetail, EventActivity, ExhibitorRegistration, RegistrationDocument

DOCUMENT_TYPES = {"PASSPORT_COPY", "COMPANY_PROFILE", "BUSINESS_CARD", "COMPANY_LOGO", "PRODUCT_CATALOGUE"}
ALLOWED_DOCUMENT_MIME = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


class IwbifService:
    @staticmethod
    async def owned_participant(db, user_id, participant_id):
        row = await db.get(ParticipantProfile, participant_id)
        if not row or row.user_id != user_id: raise HTTPException(403, "Participant profile is not owned by current user")
        return row

    @staticmethod
    async def create_registration(db: AsyncSession, event_id: UUID, user_id: UUID, payload):
        await IwbifService.owned_participant(db, user_id, payload.participant_id)
        if not await db.get(Event, event_id): raise NotFoundException("EVENT_NOT_FOUND", "Event tidak ditemukan")
        package = await db.get(DelegatePackage, payload.delegate_package_id)
        if not package or package.event_id != event_id or not package.is_active: raise ValidationException("INVALID_DELEGATE_PACKAGE", "Paket delegate tidak valid")
        activity_ids = payload.activity_ids
        valid_activities = set((await db.execute(select(EventActivity.id).where(EventActivity.event_id == event_id, EventActivity.is_active.is_(True), EventActivity.id.in_(activity_ids)))).scalars())
        if valid_activities != set(activity_ids): raise ValidationException("INVALID_ACTIVITY", "Aktivitas event tidak valid")
        existing = (await db.execute(select(Registration).where(Registration.event_id == event_id, Registration.participant_id == payload.participant_id, Registration.status.notin_([RegistrationStatus.CANCELLED, RegistrationStatus.CANCELED])))).scalar_one_or_none()
        if existing: raise ConflictException("REGISTRATION_EXISTS", "Peserta sudah memiliki registrasi aktif")
        registration = Registration(event_id=event_id, participant_id=payload.participant_id, registration_number=f"IWBIF-{uuid.uuid4().hex[:10].upper()}", status=RegistrationStatus.DRAFT)
        db.add(registration); await db.flush()
        data = payload.model_dump(exclude={"participant_id"})
        data["company_website"] = str(data["company_website"]) if data["company_website"] else None
        data["linkedin"] = str(data["linkedin"]) if data["linkedin"] else None
        data["activity_ids"] = [str(x) for x in activity_ids]
        now = datetime.now(timezone.utc)
        data.update(registration_id=registration.id, terms_accepted_at=now, consent_accepted_at=now)
        db.add(DelegateRegistrationDetail(**data)); await db.commit(); await db.refresh(registration)
        return registration

    @staticmethod
    async def owned_registration(db, registration_id, user_id):
        q = select(Registration).join(ParticipantProfile, Registration.participant_id == ParticipantProfile.id).where(Registration.id == registration_id, ParticipantProfile.user_id == user_id)
        row = (await db.execute(q)).scalar_one_or_none()
        if not row: raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
        return row

    @staticmethod
    async def read_registration(db, registration_id, user_id):
        reg = await IwbifService.owned_registration(db, registration_id, user_id); detail = await db.get(DelegateRegistrationDetail, reg.id)
        return IwbifService.serialize_registration(reg, detail)

    @staticmethod
    def serialize_registration(reg, detail):
        values = {c.name: getattr(detail, c.name) for c in detail.__table__.columns} if detail else {}
        values.pop("registration_id", None)
        return {"id": reg.id, "event_id": reg.event_id, "participant_id": reg.participant_id, "registration_number": reg.registration_number, "status": reg.status.value if hasattr(reg.status, "value") else reg.status, "detail": values}

    @staticmethod
    async def submit(db, registration_id, user_id):
        reg = await IwbifService.owned_registration(db, registration_id, user_id)
        if reg.status != RegistrationStatus.DRAFT: raise ConflictException("INVALID_REGISTRATION_STATUS", "Hanya draft yang dapat dikirim")
        passport = (await db.execute(select(RegistrationDocument.id).where(RegistrationDocument.registration_id == reg.id, RegistrationDocument.document_type == "PASSPORT_COPY"))).first()
        if not passport: raise ValidationException("PASSPORT_REQUIRED", "Passport Copy wajib diunggah sebelum submit")
        reg.status = RegistrationStatus.SUBMITTED; detail = await db.get(DelegateRegistrationDetail, reg.id); detail.submitted_at = datetime.now(timezone.utc)
        await db.commit(); return reg

    @staticmethod
    async def save_document(db, registration_id, user_id, document_type, file: UploadFile):
        await IwbifService.owned_registration(db, registration_id, user_id)
        if document_type not in DOCUMENT_TYPES: raise ValidationException("INVALID_DOCUMENT_TYPE", "Tipe dokumen tidak valid")
        extension = ALLOWED_DOCUMENT_MIME.get(file.content_type or "")
        if not extension: raise ValidationException("INVALID_DOCUMENT_MIME", "Dokumen harus PDF, JPG, atau PNG")
        content = await file.read(MAX_DOCUMENT_SIZE + 1); await file.close()
        if not content or len(content) > MAX_DOCUMENT_SIZE: raise ValidationException("INVALID_DOCUMENT_SIZE", "Dokumen kosong atau melebihi 10 MB")
        safe_original = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "document").name)[:255]
        storage_key = f"registrations/{registration_id}/{uuid.uuid4()}{extension}"
        target = Path(".private_uploads").resolve() / storage_key; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
        row = RegistrationDocument(registration_id=registration_id, document_type=document_type, original_filename=safe_original, storage_key=storage_key, mime_type=file.content_type, file_size=len(content))
        db.add(row); await db.commit(); await db.refresh(row); return row

    @staticmethod
    async def update_registration(db, registration_id, user_id, payload):
        reg = await IwbifService.owned_registration(db, registration_id, user_id)
        if reg.status != RegistrationStatus.DRAFT: raise ConflictException("REGISTRATION_NOT_EDITABLE", "Hanya draft yang dapat diubah")
        if reg.participant_id != payload.participant_id: raise ValidationException("PARTICIPANT_IMMUTABLE", "Participant tidak dapat diubah")
        package = await db.get(DelegatePackage, payload.delegate_package_id)
        if not package or package.event_id != reg.event_id or not package.is_active: raise ValidationException("INVALID_DELEGATE_PACKAGE", "Paket delegate tidak valid")
        valid_activities = set((await db.execute(select(EventActivity.id).where(EventActivity.event_id == reg.event_id, EventActivity.is_active.is_(True), EventActivity.id.in_(payload.activity_ids)))).scalars())
        if valid_activities != set(payload.activity_ids): raise ValidationException("INVALID_ACTIVITY", "Aktivitas event tidak valid")
        detail = await db.get(DelegateRegistrationDetail, reg.id); data = payload.model_dump(exclude={"participant_id"})
        data["company_website"] = str(data["company_website"]) if data["company_website"] else None; data["linkedin"] = str(data["linkedin"]) if data["linkedin"] else None; data["activity_ids"] = [str(x) for x in data["activity_ids"]]
        for key, value in data.items(): setattr(detail, key, value)
        await db.commit(); return reg

    @staticmethod
    async def create_exhibitor(db, event_id, user_id, payload):
        await IwbifService.owned_participant(db, user_id, payload.participant_id)
        if not await db.get(Event, event_id): raise NotFoundException("EVENT_NOT_FOUND", "Event tidak ditemukan")
        data = payload.model_dump(); data["email"] = str(data["email"]); data.update(event_id=event_id, exhibition_terms_accepted_at=datetime.now(timezone.utc))
        row = ExhibitorRegistration(**data); db.add(row); await db.commit(); await db.refresh(row); return row

    @staticmethod
    async def save_exhibitor_catalogue(db, exhibitor_id, user_id, file):
        row = await db.get(ExhibitorRegistration, exhibitor_id)
        participant = await db.get(ParticipantProfile, row.participant_id) if row else None
        if not row or not participant or participant.user_id != user_id: raise NotFoundException("EXHIBITOR_NOT_FOUND", "Exhibitor tidak ditemukan")
        extension = ALLOWED_DOCUMENT_MIME.get(file.content_type or "")
        if not extension: raise ValidationException("INVALID_DOCUMENT_MIME", "Katalog harus PDF, JPG, atau PNG")
        content = await file.read(MAX_DOCUMENT_SIZE + 1); await file.close()
        if not content or len(content) > MAX_DOCUMENT_SIZE: raise ValidationException("INVALID_DOCUMENT_SIZE", "Katalog kosong atau melebihi 10 MB")
        storage_key = f"exhibitors/{exhibitor_id}/{uuid.uuid4()}{extension}"; target = Path(".private_uploads").resolve() / storage_key; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
        doc = RegistrationDocument(exhibitor_id=exhibitor_id, document_type="PRODUCT_CATALOGUE", original_filename=re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "catalogue").name)[:255], storage_key=storage_key, mime_type=file.content_type, file_size=len(content))
        db.add(doc); row.status = "submitted"; await db.commit(); await db.refresh(doc); return doc
