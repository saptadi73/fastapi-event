import base64
import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.core.exceptions import ValidationException


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(body: bytes) -> str:
    return base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")


def signature_component(client_id: str, request_id: str, timestamp: str, target: str, body: bytes | None) -> str:
    values = [f"Client-Id:{client_id}", f"Request-Id:{request_id}", f"Request-Timestamp:{timestamp}", f"Request-Target:{target}"]
    if body is not None:
        values.append(f"Digest:{digest(body)}")
    return "\n".join(values)


def generate_signature(client_id: str, request_id: str, timestamp: str, target: str, body: bytes | None, secret: str) -> str:
    component = signature_component(client_id, request_id, timestamp, target, body).encode("utf-8")
    encoded = base64.b64encode(hmac.new(secret.encode("utf-8"), component, hashlib.sha256).digest()).decode("ascii")
    return f"HMACSHA256={encoded}"


def verify_signature(signature: str, client_id: str, request_id: str, timestamp: str, target: str, body: bytes, secret: str) -> bool:
    expected = generate_signature(client_id, request_id, timestamp, target, body, secret)
    return hmac.compare_digest(signature, expected)


class DokuCheckoutClient:
    def __init__(self):
        self.settings = get_settings()

    def _credentials(self):
        if not self.settings.DOKU_CLIENT_ID or not self.settings.DOKU_SECRET_KEY:
            raise ValidationException("DOKU_NOT_CONFIGURED", "DOKU Client ID dan Secret Key belum dikonfigurasi")

    async def create_payment(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        self._credentials()
        body = canonical_json(payload)
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        target = self.settings.DOKU_CHECKOUT_PATH
        headers = {
            "Client-Id": self.settings.DOKU_CLIENT_ID,
            "Request-Id": request_id,
            "Request-Timestamp": timestamp,
            "Signature": generate_signature(self.settings.DOKU_CLIENT_ID, request_id, timestamp, target, body, self.settings.DOKU_SECRET_KEY),
            "Content-Type": "application/json",
        }
        def send():
            request = Request(self.settings.DOKU_BASE_URL.rstrip("/") + target, data=body, headers=headers, method="POST")
            try:
                with urlopen(request, timeout=30) as response:
                    return response.status, dict(response.headers), response.read()
            except HTTPError as exc:
                return exc.code, dict(exc.headers), exc.read()
        try:
            status_code, response_headers, response_body = await asyncio.to_thread(send)
        except (URLError, TimeoutError, OSError) as exc:
            raise ValidationException("DOKU_UNAVAILABLE", "Tidak dapat terhubung ke DOKU") from exc
        try:
            data = json.loads(response_body)
        except ValueError as exc:
            raise ValidationException("DOKU_INVALID_RESPONSE", "Response DOKU tidak valid") from exc
        if status_code >= 400:
            message = data.get("error", {}).get("message") or data.get("message") or "DOKU menolak transaksi"
            raise ValidationException("DOKU_PAYMENT_REJECTED", str(message))
        response_signature = response_headers.get("Signature") or response_headers.get("signature")
        response_timestamp = response_headers.get("Response-Timestamp") or response_headers.get("response-timestamp")
        if response_signature and response_timestamp:
            component = "\n".join([
                f"Client-Id:{self.settings.DOKU_CLIENT_ID}", f"Request-Id:{request_id}",
                f"Response-Timestamp:{response_timestamp}", f"Request-Target:{target}",
                f"Digest:{digest(response_body)}",
            ]).encode("utf-8")
            expected = "HMACSHA256=" + base64.b64encode(hmac.new(self.settings.DOKU_SECRET_KEY.encode(), component, hashlib.sha256).digest()).decode()
            if not hmac.compare_digest(response_signature, expected):
                raise ValidationException("DOKU_INVALID_RESPONSE_SIGNATURE", "Signature response DOKU tidak valid")
        return data, request_id
