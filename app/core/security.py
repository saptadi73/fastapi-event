import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings

try:
    from passlib.context import CryptContext
except Exception:  # pragma: no cover - optional dependency
    CryptContext = None

try:
    from jose import jwt as jose_jwt
    from jose.exceptions import ExpiredSignatureError as JoseExpiredSignatureError
    from jose.exceptions import JWTError as JoseJWTError
except Exception:  # pragma: no cover - optional dependency
    jose_jwt = None
    JoseExpiredSignatureError = None
    JoseJWTError = None


class TokenDecodeError(ValueError):
    pass


class TokenExpiredError(TokenDecodeError):
    pass


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext is not None else None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _fallback_hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000, dklen=32)
    return f"fallback${_b64url_encode(salt)}${_b64url_encode(digest)}"


def _fallback_verify_password(password: str, hashed: str) -> bool:
    try:
        prefix, salt_b64, digest_b64 = hashed.split("$")
        if prefix != "fallback":
            return False
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000, dklen=32)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False


def _sign(payload: bytes, secret: str) -> str:
    return _b64url_encode(hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest())


def _fallback_encode(payload: dict[str, Any], settings) -> str:
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("utf-8")
    signature = _sign(signing_input, settings.JWT_SECRET_KEY)
    return ".".join([*segments, signature])


def _fallback_decode(token: str, settings) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenDecodeError("Invalid token")
    header_b64, payload_b64, signature = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected = _sign(signing_input, settings.JWT_SECRET_KEY)
    if not hmac.compare_digest(signature, expected):
        raise TokenDecodeError("Invalid token signature")
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenDecodeError("Invalid token payload") from exc
    exp_ts = payload.get("exp")
    if isinstance(exp_ts, int):
        if datetime.fromtimestamp(exp_ts, tz=timezone.utc) < datetime.now(timezone.utc):
            raise TokenExpiredError("Token expired")
    return payload


def hash_password(password: str) -> str:
    if _pwd_context is not None:
        return _pwd_context.hash(password)
    return _fallback_hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Fallback hashes may be created in an environment where passlib/bcrypt is
    # unavailable (for example a maintenance CLI). They must remain verifiable
    # after the database is read by a production process that does have
    # passlib installed.
    if hashed_password.startswith("fallback$"):
        return _fallback_verify_password(plain_password, hashed_password)
    if _pwd_context is None:
        return False
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except (TypeError, ValueError):
        # Treat unsupported/corrupt hashes as invalid credentials instead of
        # leaking an internal server error from the login endpoint.
        return False


def _to_timestamp(value: datetime) -> int:
    return int(value.timestamp())


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": _to_timestamp(now),
        "exp": _to_timestamp(expires),
    }
    if extra:
        payload.update(extra)
    if jose_jwt is not None:
        return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return _fallback_encode(payload, settings)


def create_refresh_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "iat": _to_timestamp(now),
        "exp": _to_timestamp(expires),
    }
    if extra:
        payload.update(extra)
    if jose_jwt is not None:
        return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return _fallback_encode(payload, settings)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if jose_jwt is not None:
        try:
            return jose_jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except JoseExpiredSignatureError as exc:
            raise TokenExpiredError("Token expired") from exc
        except JoseJWTError as exc:
            raise TokenDecodeError("Invalid token") from exc
    return _fallback_decode(token, settings)
