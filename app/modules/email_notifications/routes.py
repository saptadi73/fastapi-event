from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, require_admin
from app.core.exceptions import NotFoundException, ValidationException
from app.core.i18n import normalize_locale
from app.modules.email_notifications import schemas
from app.modules.email_notifications.models import EmailNotificationLog, EmailNotificationPreference, EmailNotificationTemplate
from app.modules.email_notifications.service import TRIGGER_VARIABLES, deliver, ensure_event_templates, render
from app.modules.users.models import User
from app.support.responses import success_response

router = APIRouter(prefix="/admin/events/{event_id}/email-notifications", tags=["admin-email-notifications"])


async def get_template(db: AsyncSession, event_id: UUID, trigger: str, locale: str = "en") -> EmailNotificationTemplate:
    if trigger not in TRIGGER_VARIABLES:
        raise ValidationException("INVALID_EMAIL_TRIGGER", "Trigger notifikasi email tidak valid")
    locale = normalize_locale(locale)
    await ensure_event_templates(db, event_id, locale)
    row = (await db.execute(select(EmailNotificationTemplate).where(EmailNotificationTemplate.event_id == event_id, EmailNotificationTemplate.trigger == trigger, EmailNotificationTemplate.locale == locale))).scalar_one_or_none()
    if not row:
        raise NotFoundException("EMAIL_TEMPLATE_NOT_FOUND", "Template email tidak ditemukan")
    return row


@router.get("/accounts/{user_id}/preferences")
async def account_preferences(event_id: UUID, user_id: UUID, request: Request, locale: str = "en", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundException("USER_NOT_FOUND", "User tidak ditemukan")
    templates = await ensure_event_templates(db, event_id, normalize_locale(locale))
    overrides = {
        row.trigger: row
        for row in (await db.execute(select(EmailNotificationPreference).where(
            EmailNotificationPreference.event_id == event_id,
            EmailNotificationPreference.user_id == user_id,
        ))).scalars().all()
    }
    data = []
    for template in templates:
        override = overrides.get(template.trigger)
        override_enabled = override.is_enabled if override else None
        data.append(schemas.AccountPreferenceRead(
            event_id=event_id,
            user_id=user_id,
            trigger=template.trigger,
            global_enabled=template.is_enabled,
            override_enabled=override_enabled,
            effective_enabled=template.is_enabled and override_enabled is not False,
            updated_by=override.updated_by if override else None,
            updated_at=override.updated_at if override else None,
        ))
    return success_response("Pengaturan notifikasi akun ditemukan", data, request=request)


@router.put("/accounts/{user_id}/preferences/{trigger}")
async def update_account_preference(event_id: UUID, user_id: UUID, trigger: str, payload: schemas.AccountPreferenceWrite, request: Request, locale: str = "en", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundException("USER_NOT_FOUND", "User tidak ditemukan")
    template = await get_template(db, event_id, trigger, locale)
    row = (await db.execute(select(EmailNotificationPreference).where(
        EmailNotificationPreference.event_id == event_id,
        EmailNotificationPreference.user_id == user_id,
        EmailNotificationPreference.trigger == trigger,
    ))).scalar_one_or_none()
    if payload.is_enabled is None:
        if row:
            await db.delete(row)
        await db.commit()
        override_enabled = None
        updated_by = None
        updated_at = None
    else:
        if row is None:
            row = EmailNotificationPreference(event_id=event_id, user_id=user_id, trigger=trigger, is_enabled=payload.is_enabled, updated_by=admin.id)
            db.add(row)
        else:
            row.is_enabled = payload.is_enabled
            row.updated_by = admin.id
        await db.commit()
        await db.refresh(row)
        override_enabled = row.is_enabled
        updated_by = row.updated_by
        updated_at = row.updated_at
    data = schemas.AccountPreferenceRead(
        event_id=event_id,
        user_id=user_id,
        trigger=trigger,
        global_enabled=template.is_enabled,
        override_enabled=override_enabled,
        effective_enabled=template.is_enabled and override_enabled is not False,
        updated_by=updated_by,
        updated_at=updated_at,
    )
    return success_response("Pengaturan notifikasi akun berhasil diperbarui", data, request=request)


@router.get("")
async def list_templates(event_id: UUID, request: Request, locale: str = "en", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    rows = await ensure_event_templates(db, event_id, normalize_locale(locale))
    return success_response("Template notifikasi email ditemukan", [schemas.TemplateRead.model_validate(row) for row in rows], request=request)


@router.put("/{trigger}")
async def update_template(event_id: UUID, trigger: str, payload: schemas.TemplateWrite, request: Request, locale: str = "en", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await get_template(db, event_id, trigger, locale)
    used = set(__import__("re").findall(r"{{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*}}", payload.subject_template + payload.body_template))
    invalid = sorted(used - set(TRIGGER_VARIABLES[trigger]))
    if invalid:
        raise ValidationException("INVALID_TEMPLATE_VARIABLE", f"Variabel tidak tersedia: {', '.join(invalid)}")
    row.is_enabled = payload.is_enabled; row.subject_template = payload.subject_template; row.body_template = payload.body_template
    await db.commit(); await db.refresh(row)
    return success_response("Template notifikasi email berhasil diperbarui", schemas.TemplateRead.model_validate(row), request=request)


@router.post("/{trigger}/preview")
async def preview(event_id: UUID, trigger: str, payload: schemas.PreviewRequest, request: Request, locale: str = "en", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await get_template(db, event_id, trigger, locale)
    requested_locale = normalize_locale(locale)
    return success_response("Preview template email", {"subject": render(row.subject_template, payload.variables), "body": render(row.body_template, payload.variables), "requested_locale": requested_locale, "used_locale": row.locale, "translation_fallback": row.locale != requested_locale}, request=request)


@router.post("/{trigger}/test-send")
async def test_send(event_id: UUID, trigger: str, payload: schemas.TestSendRequest, request: Request, locale: str = "en", admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    row = await get_template(db, event_id, trigger, locale)
    sent = await deliver(event_id, trigger, payload.recipient, payload.variables, "test", None, normalize_locale(locale))
    return success_response("Email percobaan berhasil dikirim" if sent else "Email tidak dikirim; periksa status template dan konfigurasi SMTP", {"sent": sent, "locale": row.locale}, request=request)


@router.get("/logs/history")
async def delivery_logs(event_id: UUID, request: Request, limit: int = 100, locale: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    stmt = select(EmailNotificationLog).where(EmailNotificationLog.event_id == event_id)
    if locale:
        stmt = stmt.where(EmailNotificationLog.locale == normalize_locale(locale))
    rows = (await db.execute(stmt.order_by(EmailNotificationLog.created_at.desc()).limit(min(max(limit, 1), 500)))).scalars().all()
    return success_response("Riwayat pengiriman email ditemukan", [schemas.LogRead.model_validate(row) for row in rows], request=request)
