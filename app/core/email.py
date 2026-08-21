import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _send_message(
    message: EmailMessage,
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool,
    use_tls: bool,
) -> None:
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=30) as client:
        client.ehlo()
        if use_tls and not use_ssl:
            client.starttls()
            client.ehlo()
        client.login(username, password)
        client.send_message(message)


async def send_registration_confirmation(email: str) -> None:
    settings = get_settings()
    if not settings.EMAIL_ENABLED:
        logger.info("Registration email disabled; recipient=%s", email)
        return
    if not settings.EMAIL_SMTP_PASSWORD:
        logger.error("Registration email skipped: EMAIL_SMTP_PASSWORD is empty")
        return

    login_url = settings.FRONTEND_LOGIN_URL
    message = EmailMessage()
    message["Subject"] = "Registrasi IWBIF 2026 berhasil"
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    message["To"] = email
    message.set_content(
        "Registrasi Anda berhasil dilakukan pada event IWBIF 2026.\n\n"
        f"Silakan login untuk melanjutkan pendaftaran dan memilih package:\n{login_url}\n\n"
        "Salam,\nIWBIF 2026"
    )
    try:
        await asyncio.to_thread(
            _send_message,
            message,
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_SMTP_PORT,
            settings.EMAIL_SMTP_USERNAME,
            settings.EMAIL_SMTP_PASSWORD,
            settings.EMAIL_SMTP_USE_SSL,
            settings.EMAIL_SMTP_USE_TLS,
        )
    except Exception:
        logger.exception("Failed to send registration email; recipient=%s", email)
