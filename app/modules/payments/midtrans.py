import asyncio
import base64
import hashlib
import hmac
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.core.exceptions import ValidationException


class MidtransClient:
    def __init__(self):
        self.settings = get_settings()

    @property
    def snap_base_url(self) -> str:
        host = "app.midtrans.com" if self.settings.MIDTRANS_IS_PRODUCTION else "app.sandbox.midtrans.com"
        return f"https://{host}/snap/v1"

    @property
    def api_base_url(self) -> str:
        host = "api.midtrans.com" if self.settings.MIDTRANS_IS_PRODUCTION else "api.sandbox.midtrans.com"
        return f"https://{host}/v2"

    def _authorization(self) -> str:
        if not self.settings.MIDTRANS_SERVER_KEY:
            raise ValidationException("MIDTRANS_NOT_CONFIGURED", "Midtrans Server Key belum dikonfigurasi")
        token = base64.b64encode(f"{self.settings.MIDTRANS_SERVER_KEY}:".encode()).decode()
        return f"Basic {token}"

    async def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        headers = {"Authorization": self._authorization(), "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"

        def send():
            request = Request(url, data=body, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    return response.status, response.read()
            except HTTPError as exc:
                return exc.code, exc.read()

        try:
            status, response_body = await asyncio.to_thread(send)
        except (URLError, TimeoutError, OSError) as exc:
            raise ValidationException("MIDTRANS_UNAVAILABLE", "Tidak dapat terhubung ke Midtrans") from exc
        try:
            data = json.loads(response_body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValidationException("MIDTRANS_INVALID_RESPONSE", "Response Midtrans tidak valid") from exc
        if status >= 400:
            messages = data.get("error_messages") or [data.get("status_message") or "Midtrans menolak transaksi"]
            raise ValidationException("MIDTRANS_PAYMENT_REJECTED", "; ".join(map(str, messages)))
        return data

    async def create_snap_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"{self.snap_base_url}/transactions", payload)

    async def transaction_status(self, order_id: str) -> dict[str, Any]:
        return await self._request("GET", f"{self.api_base_url}/{quote(order_id, safe='')}/status")


def verify_notification_signature(payload: dict[str, Any], server_key: str) -> bool:
    required = ("order_id", "status_code", "gross_amount", "signature_key")
    if not server_key or not all(payload.get(key) is not None for key in required):
        return False
    value = f"{payload['order_id']}{payload['status_code']}{payload['gross_amount']}{server_key}"
    expected = hashlib.sha512(value.encode()).hexdigest()
    return hmac.compare_digest(str(payload["signature_key"]), expected)


def verify_pay_account_signature(payload: dict[str, Any], server_key: str) -> bool:
    """Verify a Midtrans Pay Account linking/unlinking notification."""
    required = ("account_id", "account_status", "status_code", "signature_key")
    if not server_key or not all(payload.get(key) is not None for key in required):
        return False
    value = f"{payload['account_id']}{payload['account_status']}{payload['status_code']}{server_key}"
    expected = hashlib.sha512(value.encode()).hexdigest()
    return hmac.compare_digest(str(payload["signature_key"]), expected)


def normalize_midtrans_channel(payload: dict[str, Any]) -> str | None:
    """Return the customer-facing Midtrans rail, not its issuer/acquirer."""
    payment_type = str(payload.get("payment_type") or "").strip().lower()
    if not payment_type:
        return None
    fixed = {
        "qris": "QRIS",
        "gopay": "GOPAY",
        "shopeepay": "SHOPEEPAY",
        "credit_card": "CREDIT_CARD",
        "echannel": "MANDIRI_BILL",
        "akulaku": "AKULAKU",
        "kredivo": "KREDIVO",
    }
    if payment_type in fixed:
        return fixed[payment_type]
    if payment_type == "bank_transfer":
        bank = str(payload.get("bank") or "").strip().upper()
        return bank or "BANK_TRANSFER"
    if payment_type == "cstore":
        store = str(payload.get("store") or "").strip().upper()
        return store or "CSTORE"
    return payment_type.upper()
