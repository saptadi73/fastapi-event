"""BRI Non-SNAP inquiry. Never creates a bill or settles a payment."""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.responses import JSONResponse, Response
from sqlalchemy import select

from app.modules.payments.doku import canonical_json, digest, verify_signature
from app.modules.payments.models import Order, Payment
from app.modules.users.models import User


INQUIRY_PATH = "/api/v1/doku/va/inquiry"


async def handle_inquiry(session, body, headers, settings, target):
    client = headers.get("client-id", "")
    request_id = headers.get("request-id", "")
    timestamp = headers.get("request-timestamp", "")
    secret = settings.DOKU_SECRET_KEY
    if not secret or not settings.DOKU_CLIENT_ID:
        return JSONResponse({"message": "DOKU not configured"}, status_code=503)
    if (client != settings.DOKU_CLIENT_ID or not request_id or len(request_id) > 128
            or not verify_signature(headers.get("signature", ""), client, request_id,
                                    timestamp, target, body, secret)):
        return JSONResponse({"message": "Invalid signature"}, status_code=401)
    try:
        sent = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if sent.tzinfo is None or abs((datetime.now(timezone.utc) - sent).total_seconds()) > 300:
            raise ValueError("Stale timestamp")
    except ValueError:
        return JSONResponse({"message": "Invalid timestamp"}, status_code=401)

    def reply(status, va="", data=None):
        payload = {"virtual_account_info": {"virtual_account_number": va},
                   "virtual_account_inquiry": {"status": status}}
        if data:
            payload.update(data)
        encoded = canonical_json(payload)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        component = "\n".join([f"Client-Id:{client}", f"Request-Id:{request_id}",
                               f"Response-Timestamp:{now}", f"Request-Target:{target}",
                               f"Digest:{digest(encoded)}"])
        signature = "HMACSHA256=" + base64.b64encode(hmac.new(
            secret.encode(), component.encode(), hashlib.sha256).digest()).decode()
        code = 200 if status == "success" else 404 if status == "billing_not_found" else 400
        return Response(encoded, status_code=code, media_type="application/json", headers={
            "Client-Id": client, "Request-Id": request_id, "Response-Timestamp": now,
            "Signature": signature})

    try:
        payload = json.loads(body)
        va = payload["virtual_account_info"]["virtual_account_number"]
        if (not isinstance(va, str) or not va.isascii() or not va.isdigit() or len(va) > 18
                or payload["service"]["id"] != "VIRTUAL_ACCOUNT"
                or payload["acquirer"]["id"] != "BRI"
                or payload["channel"]["id"] != "VIRTUAL_ACCOUNT_BRI"
                or payload["virtual_account_info"].get("billing_type", "FIX_BILL") != "FIX_BILL"
                or not isinstance(payload["virtual_account_inquiry"]["date"], str)):
            return reply("decline")
    except (ValueError, KeyError, TypeError):
        return reply("decline")

    # Exact provider, bank and VA match; never infer a bill from the VA suffix.
    rows = (await session.execute(select(Payment, Order, User)
        .join(Order, Payment.order_id == Order.id).join(User, Order.user_id == User.id)
        .where(Payment.provider == "doku", Payment.virtual_account_no == va,
               Payment.channel_code.in_(["BRI", "VIRTUAL_ACCOUNT_BRI"]),
               Payment.deleted_at.is_(None)).limit(2))).all()
    if not rows:
        return reply("billing_not_found", va)
    if len(rows) != 1:
        return reply("decline", va)
    payment, order, user = rows[0]
    if payment.transaction_status == "success" or order.status == "paid":
        return reply("billing_already_paid", va)
    now = datetime.now(timezone.utc)
    def expired(value):
        return value is not None and value.replace(tzinfo=value.tzinfo or timezone.utc) <= now
    if (payment.transaction_status == "expired" or order.status == "expired"
            or expired(payment.expired_at) or expired(order.expires_at)):
        return reply("billing_was_expired", va)
    amount = Decimal(str(payment.gross_amount))
    if (payment.transaction_status not in {"created", "pending"}
            or order.status not in {"pending", "partially_paid"}
            or payment.currency != "IDR" or order.currency != "IDR"
            or not payment.provider_order_id or not user.full_name
            or not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value()
            or amount > 9999999999):
        return reply("decline", va)
    return reply("success", va, {"order": {"invoice_number": payment.provider_order_id,
                                           "amount": int(amount)},
                                 "customer": {"name": user.full_name[:20]}})
