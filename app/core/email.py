import asyncio
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

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

    login_url = frontend_login_url()
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


def _frontend_route(configured_url: str, path: str) -> str:
    settings = get_settings()
    configured_url = configured_url.strip()
    if configured_url:
        return configured_url
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}"


def frontend_login_url() -> str:
    settings = get_settings()
    return _frontend_route(settings.FRONTEND_LOGIN_URL, "/auth/login")


def password_reset_url(token: str) -> str:
    settings = get_settings()
    reset_url = _frontend_route(settings.FRONTEND_RESET_PASSWORD_URL, "/auth/reset-password")
    separator = "&" if "?" in reset_url else "?"
    return f"{reset_url}{separator}{urlencode({'token': token})}"


async def send_password_reset_email(email: str, token: str) -> bool:
    settings = get_settings()
    if not settings.EMAIL_ENABLED:
        logger.info("Password reset email disabled; recipient=%s", email)
        return False
    if not settings.EMAIL_SMTP_PASSWORD:
        logger.error("Password reset email skipped: EMAIL_SMTP_PASSWORD is empty")
        return False

    reset_url = password_reset_url(token)
    message = EmailMessage()
    message["Subject"] = "Reset your IWBIF password"
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    message["To"] = email
    message.set_content(
        "We received a request to reset your IWBIF account password.\n\n"
        f"Open this link to choose a new password:\n{reset_url}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes and can only be used once.\n"
        "If you did not request this reset, you can ignore this email.\n\n"
        "Best regards,\nThe IWBIF Team"
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
        return True
    except Exception:
        logger.exception("Failed to send password reset email; recipient=%s", email)
        return False
