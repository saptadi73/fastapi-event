import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jose import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

from app.core.config import get_settings
from app.core.exceptions import ValidationException


def minified_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def body_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(minified_json(payload)).hexdigest().lower()


def symmetric_component(method: str, path: str, token: str, payload: dict[str, Any], timestamp: str) -> str:
    return f"{method.upper()}:{path}:{token}:{body_hash(payload)}:{timestamp}"


def symmetric_signature(method: str, path: str, token: str, payload: dict[str, Any], timestamp: str, secret: str) -> str:
    component = symmetric_component(method, path, token, payload, timestamp).encode()
    return base64.b64encode(hmac.new(secret.encode(), component, hashlib.sha512).digest()).decode()


def verify_symmetric_signature(signature: str, method: str, path: str, token: str, payload: dict[str, Any], timestamp: str, secret: str) -> bool:
    return hmac.compare_digest(signature, symmetric_signature(method, path, token, payload, timestamp, secret))


def _read_key(path_value: str, label: str) -> bytes:
    if not path_value:
        raise ValidationException("DOKU_SNAP_NOT_CONFIGURED", f"{label} belum dikonfigurasi")
    path = Path(path_value).expanduser().resolve()
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValidationException("DOKU_SNAP_KEY_UNAVAILABLE", f"{label} tidak dapat dibaca") from exc


def asymmetric_signature(client_id: str, timestamp: str, private_key_path: str) -> str:
    key = serialization.load_pem_private_key(_read_key(private_key_path, "DOKU SNAP private key"), password=None)
    signed = key.sign(f"{client_id}|{timestamp}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signed).decode()


def verify_asymmetric_signature(signature: str, client_id: str, timestamp: str, public_key_path: str) -> bool:
    try:
        key = serialization.load_pem_public_key(_read_key(public_key_path, "DOKU public key"))
        key.verify(base64.b64decode(signature), f"{client_id}|{timestamp}".encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationException("DOKU_SNAP_INVALID_TIMESTAMP", "Format X-TIMESTAMP tidak valid") from exc
    if parsed.tzinfo is None:
        raise ValidationException("DOKU_SNAP_INVALID_TIMESTAMP", "X-TIMESTAMP wajib memiliki timezone")
    return parsed.astimezone(timezone.utc)


def ensure_fresh_timestamp(value: str) -> None:
    settings = get_settings()
    delta = abs((datetime.now(timezone.utc) - parse_timestamp(value)).total_seconds())
    if delta > settings.DOKU_SNAP_TIMESTAMP_TOLERANCE_SECONDS:
        raise ValidationException("DOKU_SNAP_EXPIRED_REQUEST", "X-TIMESTAMP berada di luar toleransi")


def issue_merchant_token(subject: str) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ttl = settings.DOKU_SNAP_TOKEN_TTL_SECONDS
    claims = {"iss": settings.DOKU_SNAP_PARTNER_ID, "sub": subject, "iat": int(now.timestamp()), "exp": int((now + timedelta(seconds=ttl)).timestamp()), "jti": secrets.token_hex(16)}
    key = _read_key(settings.DOKU_SNAP_PRIVATE_KEY_PATH, "DOKU SNAP private key")
    return jwt.encode(claims, key, algorithm="RS256"), ttl


def verify_merchant_token(token: str) -> bool:
    settings = get_settings()
    try:
        private_key = serialization.load_pem_private_key(_read_key(settings.DOKU_SNAP_PRIVATE_KEY_PATH, "DOKU SNAP private key"), password=None)
        public_key = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        jwt.decode(token, public_key, algorithms=["RS256"], issuer=settings.DOKU_SNAP_PARTNER_ID)
        return True
    except Exception:
        return False


class DokuSnapClient:
    _token: str | None = None
    _token_expires_at: datetime | None = None

    def __init__(self) -> None:
        self.settings = get_settings()

    def _validate(self) -> None:
        if not self.settings.DOKU_SNAP_PARTNER_ID or not self.settings.DOKU_SNAP_CLIENT_SECRET:
            raise ValidationException("DOKU_SNAP_NOT_CONFIGURED", "Partner ID dan Client Secret SNAP belum dikonfigurasi")

    async def _send(self, path: str, headers: dict[str, str], payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        body = minified_json(payload)
        def send():
            req = Request(self.settings.DOKU_BASE_URL.rstrip("/") + path, data=body, headers=headers, method="POST")
            try:
                with urlopen(req, timeout=30) as response:
                    return response.status, dict(response.headers), response.read()
            except HTTPError as exc:
                return exc.code, dict(exc.headers), exc.read()
        try:
            status, response_headers, response_body = await asyncio.to_thread(send)
        except (URLError, TimeoutError, OSError) as exc:
            raise ValidationException("DOKU_UNAVAILABLE", "Tidak dapat terhubung ke DOKU sandbox") from exc
        try:
            data = json.loads(response_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationException("DOKU_INVALID_RESPONSE", "Respons DOKU bukan JSON yang valid") from exc
        if status >= 400 or not str(data.get("responseCode", "")).startswith("200"):
            raise ValidationException("DOKU_SNAP_REJECTED", str(data.get("responseMessage") or "DOKU menolak permintaan"))
        return data, response_headers

    async def access_token(self) -> str:
        self._validate()
        now = datetime.now(timezone.utc)
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token
        timestamp = now.isoformat(timespec="seconds")
        path = self.settings.DOKU_SNAP_TOKEN_PATH
        headers = {"X-CLIENT-KEY": self.settings.DOKU_SNAP_PARTNER_ID, "X-TIMESTAMP": timestamp, "X-SIGNATURE": asymmetric_signature(self.settings.DOKU_SNAP_PARTNER_ID, timestamp, self.settings.DOKU_SNAP_PRIVATE_KEY_PATH), "Content-Type": "application/json"}
        data, _ = await self._send(path, headers, {"grantType": "client_credentials"})
        token = data.get("accessToken")
        if not token:
            raise ValidationException("DOKU_SNAP_TOKEN_MISSING", "DOKU tidak mengembalikan access token")
        ttl = max(30, int(data.get("expiresIn", 900)) - 30)
        self.__class__._token = token
        self.__class__._token_expires_at = now + timedelta(seconds=ttl)
        return token

    def va_channels(self) -> dict[str, dict[str, str]]:
        try:
            value = json.loads(self.settings.DOKU_SNAP_VA_CHANNELS_JSON)
        except ValueError as exc:
            raise ValidationException("DOKU_SNAP_INVALID_CONFIG", "DOKU_SNAP_VA_CHANNELS_JSON tidak valid") from exc
        return {str(k).upper(): v for k, v in value.items() if isinstance(v, dict)}

    def direct_debit_channels(self) -> dict[str, dict[str, str]]:
        try:
            value = json.loads(self.settings.DOKU_SNAP_DIRECT_DEBIT_CHANNELS_JSON)
        except ValueError as exc:
            raise ValidationException("DOKU_DIRECT_DEBIT_INVALID_CONFIG", "DOKU_SNAP_DIRECT_DEBIT_CHANNELS_JSON tidak valid") from exc
        return {str(key).upper(): item for key, item in value.items() if isinstance(item, dict)}

    def e_wallet_channels(self) -> dict[str, dict[str, str]]:
        try:
            value = json.loads(self.settings.DOKU_SNAP_EWALLET_CHANNELS_JSON)
        except ValueError as exc:
            raise ValidationException("DOKU_EWALLET_INVALID_CONFIG", "DOKU_SNAP_EWALLET_CHANNELS_JSON tidak valid") from exc
        return {str(key).upper(): item for key, item in value.items() if isinstance(item, dict)}

    async def direct_debit_request(self, channel_code: str, path: str, payload: dict[str, Any], *, customer_token: str | None = None) -> tuple[dict[str, Any], str]:
        """Send a channel-specific SNAP Direct Debit request.

        DOKU issues Consumer Key/Secret per Direct Debit channel; they must not
        be conflated with the merchant's VA credential.
        """
        config = self.direct_debit_channels().get(channel_code.upper())
        if not config:
            raise ValidationException("DOKU_DIRECT_DEBIT_CHANNEL_NOT_CONFIGURED", f"Direct Debit {channel_code.upper()} belum dikonfigurasi")
        partner_id = str(config.get("consumer_key") or self.settings.DOKU_SNAP_PARTNER_ID)
        secret = str(config.get("consumer_secret") or self.settings.DOKU_SNAP_CLIENT_SECRET)
        if not partner_id or not secret:
            raise ValidationException("DOKU_DIRECT_DEBIT_NOT_CONFIGURED", "Consumer Key/Secret Direct Debit belum dikonfigurasi")
        token = await self.access_token()
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        external_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"{secrets.randbelow(10**8):08d}"
        headers = {
            "X-TIMESTAMP": timestamp,
            "X-PARTNER-ID": partner_id,
            "X-EXTERNAL-ID": external_id,
            "CHANNEL-ID": self.settings.DOKU_SNAP_CHANNEL_ID,
            "Authorization": f"Bearer {token}",
            "X-SIGNATURE": symmetric_signature("POST", path, token, payload, timestamp, secret),
            "Content-Type": "application/json",
        }
        if customer_token:
            headers["Authorization-Customer"] = f"Bearer {customer_token}"
        data, _ = await self._send(path, headers, payload)
        return data, external_id

    async def create_va(self, bank_code: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        self._validate()
        config = self.va_channels().get(bank_code.upper())
        if not config or not config.get("partner_service_id"):
            raise ValidationException("DOKU_VA_CHANNEL_NOT_CONFIGURED", f"VA {bank_code.upper()} belum dikonfigurasi")
        path = config.get("create_path", self.settings.DOKU_SNAP_VA_CREATE_PATH)
        payload["partnerServiceId"] = config["partner_service_id"]
        if "customer_no" in config:
            payload["customerNo"] = str(config["customer_no"])
        token = await self.access_token()
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        external_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"{secrets.randbelow(10**8):08d}"
        headers = {"X-TIMESTAMP": timestamp, "X-PARTNER-ID": self.settings.DOKU_SNAP_PARTNER_ID, "X-EXTERNAL-ID": external_id, "CHANNEL-ID": self.settings.DOKU_SNAP_CHANNEL_ID, "Authorization": f"Bearer {token}", "X-SIGNATURE": symmetric_signature("POST", path, token, payload, timestamp, self.settings.DOKU_SNAP_CLIENT_SECRET), "Content-Type": "application/json"}
        data, _ = await self._send(path, headers, payload)
        return data, external_id

    async def create_qris(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        self._validate()
        if not self.settings.DOKU_QRIS_MERCHANT_ID or not self.settings.DOKU_QRIS_TERMINAL_ID:
            raise ValidationException("DOKU_QRIS_NOT_CONFIGURED", "Merchant ID atau Terminal ID QRIS belum dikonfigurasi")
        path = self.settings.DOKU_SNAP_QRIS_GENERATE_PATH
        payload["merchantId"] = self.settings.DOKU_QRIS_MERCHANT_ID
        payload["terminalId"] = self.settings.DOKU_QRIS_TERMINAL_ID
        token = await self.access_token()
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        external_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"{secrets.randbelow(10**8):08d}"
        headers = {"X-TIMESTAMP": timestamp, "X-PARTNER-ID": self.settings.DOKU_SNAP_PARTNER_ID, "X-EXTERNAL-ID": external_id, "CHANNEL-ID": self.settings.DOKU_SNAP_CHANNEL_ID, "Authorization": f"Bearer {token}", "X-SIGNATURE": symmetric_signature("POST", path, token, payload, timestamp, self.settings.DOKU_SNAP_CLIENT_SECRET), "Content-Type": "application/json"}
        data, _ = await self._send(path, headers, payload)
        return data, external_id
