import asyncio
import logging
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.email import _send_message
from app.modules.email_notifications.models import EmailNotificationLog, EmailNotificationTemplate
from app.modules.users.models import User

logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"{{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*}}")

TRIGGER_VARIABLES = {
    "account_registered": ["participant_name", "event_name", "login_url"],
    "registration_submitted": ["participant_name", "event_name", "registration_number", "login_url"],
    "delegate_package_selected": ["participant_name", "event_name", "package_name", "package_code", "amount", "currency", "login_url"],
    "exhibitor_package_selected": ["participant_name", "event_name", "package_name", "package_code", "amount", "currency", "login_url"],
    "payment_confirmed": ["participant_name", "event_name", "order_number", "amount", "currency", "paid_at", "login_url"],
    "business_matching_profile_saved": ["participant_name", "event_name", "login_url"],
    "meeting_requested": ["participant_name", "event_name", "counterparty_name", "meeting_topic", "login_url"],
    "meeting_accepted": ["participant_name", "event_name", "counterparty_name", "meeting_topic", "login_url"],
    "meeting_confirmed": ["participant_name", "event_name", "counterparty_name", "meeting_topic", "meeting_schedule", "meeting_venue", "login_url"],
    "meeting_declined": ["participant_name", "event_name", "counterparty_name", "meeting_topic", "login_url"],
    "meeting_cancelled": ["participant_name", "event_name", "counterparty_name", "meeting_topic", "login_url"],
    "meeting_reschedule_requested": ["participant_name", "event_name", "counterparty_name", "meeting_topic", "login_url"],
}

DEFAULT_TEMPLATES = {
    "account_registered": ("Registrasi akun IWBIF berhasil", "Halo {{ participant_name }},\n\nAkun Anda untuk {{ event_name }} telah berhasil dibuat. Silakan login untuk melanjutkan pendaftaran.\n\n{{ login_url }}"),
    "registration_submitted": ("Registrasi {{ registration_number }} telah diterima", "Halo {{ participant_name }},\n\nRegistrasi Anda untuk {{ event_name }} telah diterima. Nomor registrasi: {{ registration_number }}.\n\n{{ login_url }}"),
    "delegate_package_selected": ("Paket delegate {{ package_name }} dipilih", "Halo {{ participant_name }},\n\nAnda memilih paket delegate {{ package_name }} ({{ package_code }}) senilai {{ currency }} {{ amount }} untuk {{ event_name }}.\n\n{{ login_url }}"),
    "exhibitor_package_selected": ("Paket exhibitor {{ package_name }} dipilih", "Halo {{ participant_name }},\n\nAnda memilih paket exhibitor {{ package_name }} ({{ package_code }}) senilai {{ currency }} {{ amount }} untuk {{ event_name }}.\n\n{{ login_url }}"),
    "payment_confirmed": ("Pembayaran {{ order_number }} telah dikonfirmasi", "Halo {{ participant_name }},\n\nPembayaran {{ order_number }} sebesar {{ currency }} {{ amount }} telah dikonfirmasi pada {{ paid_at }}.\n\n{{ login_url }}"),
    "business_matching_profile_saved": ("Profil business matching tersimpan", "Halo {{ participant_name }},\n\nProfil business matching Anda untuk {{ event_name }} telah tersimpan.\n\n{{ login_url }}"),
    "meeting_requested": ("Permintaan business matching baru", "Halo {{ participant_name }},\n\n{{ counterparty_name }} mengirim permintaan meeting mengenai {{ meeting_topic }} pada {{ event_name }}.\n\n{{ login_url }}"),
    "meeting_accepted": ("Permintaan meeting diterima", "Halo {{ participant_name }},\n\n{{ counterparty_name }} menerima permintaan meeting mengenai {{ meeting_topic }}.\n\n{{ login_url }}"),
    "meeting_confirmed": ("Jadwal meeting telah dikonfirmasi", "Halo {{ participant_name }},\n\nMeeting dengan {{ counterparty_name }} mengenai {{ meeting_topic }} telah dijadwalkan: {{ meeting_schedule }}, lokasi {{ meeting_venue }}.\n\n{{ login_url }}"),
    "meeting_declined": ("Permintaan meeting ditolak", "Halo {{ participant_name }},\n\n{{ counterparty_name }} menolak permintaan meeting mengenai {{ meeting_topic }}.\n\n{{ login_url }}"),
    "meeting_cancelled": ("Meeting dibatalkan", "Halo {{ participant_name }},\n\nMeeting dengan {{ counterparty_name }} mengenai {{ meeting_topic }} telah dibatalkan.\n\n{{ login_url }}"),
    "meeting_reschedule_requested": ("Perubahan jadwal meeting diminta", "Halo {{ participant_name }},\n\n{{ counterparty_name }} meminta perubahan jadwal meeting mengenai {{ meeting_topic }}.\n\n{{ login_url }}"),
}


def render(template: str, variables: dict[str, object]) -> str:
    return TOKEN_PATTERN.sub(lambda match: str(variables.get(match.group(1), "")), template)


async def ensure_event_templates(db, event_id: UUID) -> list[EmailNotificationTemplate]:
    existing = {row.trigger: row for row in (await db.execute(select(EmailNotificationTemplate).where(EmailNotificationTemplate.event_id == event_id))).scalars()}
    for trigger, (subject, body) in DEFAULT_TEMPLATES.items():
        if trigger not in existing:
            row = EmailNotificationTemplate(event_id=event_id, trigger=trigger, subject_template=subject, body_template=body, available_variables=TRIGGER_VARIABLES[trigger])
            db.add(row); existing[trigger] = row
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    rows = (await db.execute(select(EmailNotificationTemplate).where(EmailNotificationTemplate.event_id == event_id))).scalars().all()
    return sorted(rows, key=lambda row: row.trigger)


async def deliver(event_id: UUID, trigger: str, recipient: str, variables: dict[str, object], entity_type: str | None = None, entity_id: UUID | None = None) -> bool:
    settings = get_settings()
    if not settings.EMAIL_ENABLED:
        return False
    async with AsyncSessionFactory() as db:
        await ensure_event_templates(db, event_id)
        template = (await db.execute(select(EmailNotificationTemplate).where(EmailNotificationTemplate.event_id == event_id, EmailNotificationTemplate.trigger == trigger))).scalar_one_or_none()
        if not template or not template.is_enabled:
            return False
        if entity_id and entity_type != "test":
            already_sent = (await db.execute(select(EmailNotificationLog.id).where(EmailNotificationLog.event_id == event_id, EmailNotificationLog.trigger == trigger, EmailNotificationLog.recipient == recipient, EmailNotificationLog.entity_type == entity_type, EmailNotificationLog.entity_id == entity_id, EmailNotificationLog.status == "sent").limit(1))).scalar_one_or_none()
            if already_sent:
                return True
        subject, body = render(template.subject_template, variables), render(template.body_template, variables)
        log = EmailNotificationLog(event_id=event_id, template_id=template.id, trigger=trigger, recipient=recipient, subject=subject, entity_type=entity_type, entity_id=entity_id)
        db.add(log); await db.commit(); await db.refresh(log)
        message = EmailMessage(); message["Subject"] = subject; message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"; message["To"] = recipient; message.set_content(body)
        try:
            await asyncio.to_thread(_send_message, message, settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, settings.EMAIL_SMTP_USERNAME, settings.EMAIL_SMTP_PASSWORD, settings.EMAIL_SMTP_USE_SSL, settings.EMAIL_SMTP_USE_TLS)
            log.status = "sent"; log.sent_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.exception("Email notification failed; trigger=%s recipient=%s", trigger, recipient)
            log.status = "failed"; log.error_message = str(exc)[:2000]
        await db.commit()
        return log.status == "sent"


async def deliver_to_user(event_id: UUID, trigger: str, user_id: UUID, variables: dict[str, object], entity_type: str | None = None, entity_id: UUID | None = None) -> bool:
    async with AsyncSessionFactory() as db:
        user = await db.get(User, user_id)
    if not user:
        return False
    values = {"participant_name": user.full_name or user.email, "login_url": get_settings().FRONTEND_LOGIN_URL, **variables}
    return await deliver(event_id, trigger, user.email, values, entity_type, entity_id)


async def deliver_account_registration(user_id: UUID) -> bool:
    from app.core.email import send_registration_confirmation
    from app.modules.events.models import Event

    async with AsyncSessionFactory() as db:
        user = await db.get(User, user_id)
        event = (await db.execute(select(Event).order_by(Event.start_at.desc()).limit(1))).scalar_one_or_none()
    if not user:
        return False
    if not event:
        await send_registration_confirmation(user.email)
        return True
    return await deliver_to_user(event.id, "account_registered", user.id, {"event_name": event.name}, "user", user.id)


async def deliver_payment_for_order(order_id: UUID) -> bool:
    from app.modules.events.models import Event
    from app.modules.payments.models import Order, Payment
    from app.modules.registrations.models import Registration
    from app.modules.store.models import OrderItem, Product

    async with AsyncSessionFactory() as db:
        order = await db.get(Order, order_id)
        if not order:
            return False
        event_id = None
        if order.registration_id:
            registration = await db.get(Registration, order.registration_id)
            event_id = registration.event_id if registration else None
        if event_id is None:
            event_id = (await db.execute(select(Product.event_id).join(OrderItem, OrderItem.product_id == Product.id).where(OrderItem.order_id == order.id).limit(1))).scalar_one_or_none()
        event = await db.get(Event, event_id) if event_id else None
        payment = (await db.execute(select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc()).limit(1))).scalar_one_or_none()
        user_id = order.user_id
    if not event:
        return False
    paid_at = payment.paid_at if payment else None
    return await deliver_to_user(event.id, "payment_confirmed", user_id, {"event_name": event.name, "order_number": order.order_number, "amount": order.total_amount, "currency": order.currency, "paid_at": paid_at.isoformat() if paid_at else ""}, "order", order.id)


async def deliver_meeting_update(meeting_id: UUID, trigger: str, target_user_id: UUID, actor_participant_id: UUID) -> bool:
    from app.modules.business_matching.models import Meeting, MeetingResource, MeetingSlot
    from app.modules.events.models import Event
    from app.modules.participants.models import ParticipantProfile

    async with AsyncSessionFactory() as db:
        meeting = await db.get(Meeting, meeting_id)
        if not meeting:
            return False
        event = await db.get(Event, meeting.event_id)
        actor = await db.get(ParticipantProfile, actor_participant_id)
        slot = await db.get(MeetingSlot, meeting.confirmed_slot_id) if meeting.confirmed_slot_id else None
        resource = await db.get(MeetingResource, meeting.venue_resource_id) if meeting.venue_resource_id else None
    values = {
        "event_name": event.name if event else "",
        "counterparty_name": actor.full_name if actor else "Participant",
        "meeting_topic": meeting.topic,
        "meeting_schedule": f"{slot.starts_at.isoformat()} - {slot.ends_at.isoformat()}" if slot else "",
        "meeting_venue": resource.name if resource else "",
    }
    return await deliver_to_user(meeting.event_id, trigger, target_user_id, values, "meeting", meeting.id)
