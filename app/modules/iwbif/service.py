import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.events.models import Event
from app.modules.participants.models import ParticipantProfile
from app.modules.payments.models import Order, OrderStatus
from app.modules.registrations.models import Registration, RegistrationStatus
from app.modules.store.models import OrderItem, Product
from app.modules.users.models import User
from .models import (AccommodationTravel, BusinessMatchingProfileSlot, BusinessMatchingSlot,
    Company, DelegatePackage, DelegateRegistrationDetail, EventActivity,
    ExhibitorRegistration, RegistrationActivity, RegistrationDocument,
    RegistrationParticipationCategory)

DOCUMENT_TYPES = {"PASSPORT_COPY", "COMPANY_PROFILE", "BUSINESS_CARD", "COMPANY_LOGO", "PRODUCT_CATALOGUE"}
ALLOWED_DOCUMENT_MIME = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


class IwbifService:
    @staticmethod
    async def account_country(db, user_id) -> str:
        user = await db.get(User, user_id)
        if not user or not user.country:
            raise ValidationException("USER_COUNTRY_REQUIRED", "Country akun wajib diisi sebelum registrasi")
        return user.country

    @staticmethod
    async def resolve_participant(db, user_id, participant_id=None, *, full_name=None, organization_name=None):
        row = (await db.execute(select(ParticipantProfile).where(ParticipantProfile.user_id == user_id))).scalar_one_or_none()
        if row and participant_id and row.id != participant_id:
            raise HTTPException(403, "Participant profile is not owned by current user")
        if row:
            return row
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(401, "Authenticated user not found")
        row = ParticipantProfile(
            user_id=user.id,
            full_name=full_name or user.full_name,
            organization_name=organization_name,
        )
        db.add(row)
        await db.flush()
        if participant_id and row.id != participant_id:
            raise HTTPException(403, "Participant profile is not owned by current user")
        return row

    @staticmethod
    async def owned_participant(db, user_id, participant_id):
        return await IwbifService.resolve_participant(db, user_id, participant_id)

    @staticmethod
    async def upsert_company(db, participant_id, *, name, country, address=None, website=None):
        row = (await db.execute(select(Company).where(Company.participant_id == participant_id))).scalar_one_or_none()
        if row is None:
            row = Company(participant_id=participant_id, name=name, country=country)
            db.add(row)
        row.name = name
        row.country = country
        row.address = address
        row.website = str(website) if website else None
        await db.flush()
        return row

    @staticmethod
    async def replace_registration_relations(db, registration_id, payload):
        await db.execute(delete(RegistrationParticipationCategory).where(RegistrationParticipationCategory.registration_id == registration_id))
        await db.execute(delete(RegistrationActivity).where(RegistrationActivity.registration_id == registration_id))
        db.add_all(RegistrationParticipationCategory(registration_id=registration_id, category=x) for x in payload.participation_categories)
        db.add_all(RegistrationActivity(registration_id=registration_id, activity_id=x) for x in payload.activity_ids)
        accommodation = await db.get(AccommodationTravel, registration_id)
        if accommodation is None:
            accommodation = AccommodationTravel(registration_id=registration_id)
            db.add(accommodation)
        for key in ("room_preference", "preferred_roommate", "arrival_date", "departure_date", "flight_number", "airport", "need_airport_pickup"):
            setattr(accommodation, key, getattr(payload, key))

    @staticmethod
    async def create_registration(db: AsyncSession, event_id: UUID, user_id: UUID, payload):
        participant = await IwbifService.resolve_participant(db, user_id, payload.participant_id, full_name=payload.full_name, organization_name=payload.company_organization)
        if not await db.get(Event, event_id): raise NotFoundException("EVENT_NOT_FOUND", "Event tidak ditemukan")
        package = await db.get(DelegatePackage, payload.delegate_package_id)
        if not package or package.event_id != event_id or not package.is_active: raise ValidationException("INVALID_DELEGATE_PACKAGE", "Paket delegate tidak valid")
        activity_ids = payload.activity_ids
        valid_activities = set((await db.execute(select(EventActivity.id).where(EventActivity.event_id == event_id, EventActivity.is_active.is_(True), EventActivity.id.in_(activity_ids)))).scalars())
        if valid_activities != set(activity_ids): raise ValidationException("INVALID_ACTIVITY", "Aktivitas event tidak valid")
        existing = (await db.execute(select(Registration).where(Registration.event_id == event_id, Registration.participant_id == participant.id, Registration.status.notin_([RegistrationStatus.CANCELLED, RegistrationStatus.CANCELED])))).scalar_one_or_none()
        if existing: raise ConflictException("REGISTRATION_EXISTS", "Peserta sudah memiliki registrasi aktif")
        registration = Registration(event_id=event_id, participant_id=participant.id, registration_number=f"IWBIF-{uuid.uuid4().hex[:10].upper()}", status=RegistrationStatus.DRAFT)
        db.add(registration); await db.flush()
        company = await IwbifService.upsert_company(db, participant.id, name=payload.company_organization, country=await IwbifService.account_country(db, user_id), address=payload.company_address, website=payload.company_website)
        data = payload.model_dump(exclude={"participant_id"})
        data["company_website"] = str(data["company_website"]) if data["company_website"] else None
        data["linkedin"] = str(data["linkedin"]) if data["linkedin"] else None
        data["activity_ids"] = [str(x) for x in activity_ids]
        now = datetime.now(timezone.utc)
        data.update(registration_id=registration.id, company_id=company.id, terms_accepted_at=now, consent_accepted_at=now)
        db.add(DelegateRegistrationDetail(**data)); await db.flush()
        await IwbifService.replace_registration_relations(db, registration.id, payload)
        purchased_order = (await db.execute(
            select(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(
                Order.user_id == user_id,
                Order.registration_id.is_(None),
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID]),
                Product.event_id == event_id,
                Product.code == f"DELEGATE_{package.code}",
            )
            .order_by(Order.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if purchased_order:
            purchased_order.registration_id = registration.id
        await db.commit(); await db.refresh(registration)
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
    async def submit(db, event_id, registration_id, user_id):
        reg = await IwbifService.owned_registration(db, registration_id, user_id)
        if reg.event_id != event_id:
            raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
        if reg.status != RegistrationStatus.DRAFT: raise ConflictException("INVALID_REGISTRATION_STATUS", "Hanya draft yang dapat dikirim")
        passport = (await db.execute(select(RegistrationDocument.id).where(RegistrationDocument.registration_id == reg.id, RegistrationDocument.document_type == "PASSPORT_COPY"))).first()
        if not passport: raise ValidationException("PASSPORT_REQUIRED", "Passport Copy wajib diunggah sebelum submit")
        reg.status = RegistrationStatus.SUBMITTED; detail = await db.get(DelegateRegistrationDetail, reg.id); detail.submitted_at = datetime.now(timezone.utc)
        await db.commit(); return reg

    @staticmethod
    async def save_document(db, registration_id, user_id, document_type, file: UploadFile):
        registration = await IwbifService.owned_registration(db, registration_id, user_id)
        if registration.status != RegistrationStatus.DRAFT:
            raise ConflictException("REGISTRATION_NOT_EDITABLE", "Dokumen hanya dapat diunggah saat registrasi masih draft")
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
    async def update_registration(db, event_id, registration_id, user_id, payload):
        reg = await IwbifService.owned_registration(db, registration_id, user_id)
        if reg.event_id != event_id:
            raise NotFoundException("REGISTRATION_NOT_FOUND", "Registrasi tidak ditemukan")
        if reg.status != RegistrationStatus.DRAFT: raise ConflictException("REGISTRATION_NOT_EDITABLE", "Hanya draft yang dapat diubah")
        if payload.participant_id and reg.participant_id != payload.participant_id: raise ValidationException("PARTICIPANT_IMMUTABLE", "Participant tidak dapat diubah")
        package = await db.get(DelegatePackage, payload.delegate_package_id)
        if not package or package.event_id != reg.event_id or not package.is_active: raise ValidationException("INVALID_DELEGATE_PACKAGE", "Paket delegate tidak valid")
        valid_activities = set((await db.execute(select(EventActivity.id).where(EventActivity.event_id == reg.event_id, EventActivity.is_active.is_(True), EventActivity.id.in_(payload.activity_ids)))).scalars())
        if valid_activities != set(payload.activity_ids): raise ValidationException("INVALID_ACTIVITY", "Aktivitas event tidak valid")
        detail = await db.get(DelegateRegistrationDetail, reg.id)
        company = await IwbifService.upsert_company(db, reg.participant_id, name=payload.company_organization, country=await IwbifService.account_country(db, user_id), address=payload.company_address, website=payload.company_website)
        data = payload.model_dump(exclude={"participant_id"})
        data["company_website"] = str(data["company_website"]) if data["company_website"] else None; data["linkedin"] = str(data["linkedin"]) if data["linkedin"] else None; data["activity_ids"] = [str(x) for x in data["activity_ids"]]
        data["company_id"] = company.id
        for key, value in data.items(): setattr(detail, key, value)
        await IwbifService.replace_registration_relations(db, reg.id, payload)
        await db.commit(); return reg

    @staticmethod
    async def require_paid_order(db, registration_id):
        paid_order_id = (await db.execute(
            select(Order.id)
            .where(Order.registration_id == registration_id, Order.status == OrderStatus.PAID)
            .limit(1)
        )).scalar_one_or_none()
        if paid_order_id is None:
            raise ConflictException("REGISTRATION_PAYMENT_REQUIRED", "Pembayaran registrasi belum berhasil")

    @staticmethod
    async def create_exhibitor(db, event_id, user_id, payload):
        participant = await IwbifService.resolve_participant(db, user_id, payload.participant_id, full_name=payload.contact_person, organization_name=payload.company_name)
        if not await db.get(Event, event_id): raise NotFoundException("EVENT_NOT_FOUND", "Event tidak ditemukan")
        existing = (await db.execute(select(ExhibitorRegistration.id).where(ExhibitorRegistration.event_id == event_id, ExhibitorRegistration.participant_id == participant.id))).first()
        if existing: raise ConflictException("EXHIBITOR_EXISTS", "User sudah memiliki registrasi exhibitor untuk event ini")
        company = await IwbifService.upsert_company(db, participant.id, name=payload.company_name, country=await IwbifService.account_country(db, user_id))
        data = payload.model_dump(exclude={"participant_id"}); data["email"] = str(data["email"]); data.update(event_id=event_id, participant_id=participant.id, company_id=company.id, exhibition_terms_accepted_at=datetime.now(timezone.utc))
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
