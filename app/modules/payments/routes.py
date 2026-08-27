import json
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db_session, require_admin
from app.modules.users.models import User
from app.support.responses import success_response
from app.modules.payments import schemas
from app.modules.payments.service import PaymentService
from app.modules.payments.doku_snap import DokuSnapClient
from app.modules.payments.midtrans import verify_pay_account_signature
from app.modules.payments.reporting import PAYMENT_STATUSES, PaymentReportingService
from app.core.exceptions import AppException, ValidationException
from app.core.config import get_settings
from app.modules.payments.models import Order, Payment, PaymentChannel, PaymentProof, PaymentWebhookCapture
from app.core.exceptions import NotFoundException
from app.modules.email_notifications.service import deliver_payment_for_order

router = APIRouter(tags=["payments"])
logger = logging.getLogger(__name__)

_WEBHOOK_CAPTURE_HEADERS = {
    "content-type", "content-length", "user-agent", "host",
    "x-forwarded-for", "x-forwarded-proto", "x-request-id",
}


async def _capture_webhook(request: Request, db: AsyncSession, provider: str) -> tuple[bytes, uuid.UUID]:
    body = await request.body()
    capture = PaymentWebhookCapture(
        provider=provider,
        content_type=request.headers.get("content-type"),
        headers={key.lower(): value for key, value in request.headers.items() if key.lower() in _WEBHOOK_CAPTURE_HEADERS},
        raw_body=body.decode("utf-8", errors="replace"),
    )
    db.add(capture)
    await db.commit()
    return body, capture.id


async def _parse_captured_webhook(body: bytes, capture_id: uuid.UUID, db: AsyncSession) -> dict:
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    capture = await db.get(PaymentWebhookCapture, capture_id)
    capture.parsed_payload = payload
    await db.commit()
    return payload


async def _complete_webhook_capture(capture_id: uuid.UUID, db: AsyncSession, result: str) -> None:
    capture = await db.get(PaymentWebhookCapture, capture_id)
    capture.processing_status = "processed"
    capture.processing_result = result
    capture.processed_at = datetime.now().astimezone()
    await db.commit()


async def _fail_webhook_capture(capture_id: uuid.UUID, db: AsyncSession, exc: Exception) -> None:
    await db.rollback()
    capture = await db.get(PaymentWebhookCapture, capture_id)
    capture.processing_status = "failed"
    capture.error_code = getattr(exc, "code", exc.__class__.__name__)
    capture.error_message = str(getattr(exc, "message", exc))[:2000]
    capture.processed_at = datetime.now().astimezone()
    await db.commit()


@router.get("/payments/methods", summary="List active payment methods for frontend")
async def list_payment_methods(request: Request, db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(PaymentChannel).where(PaymentChannel.is_enabled.is_(True)).order_by(PaymentChannel.sort_order, PaymentChannel.display_name))).scalars().all()
    return success_response("Metode pembayaran aktif", data=[schemas.PublicPaymentMethodRead.model_validate(row) for row in rows], request=request)


@router.get("/admin/payment-channels", summary="List payment channel catalog")
async def admin_list_payment_channels(request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(select(PaymentChannel).order_by(PaymentChannel.sort_order, PaymentChannel.display_name))).scalars().all()
    return success_response("Katalog payment channel", data=[schemas.PaymentChannelRead.model_validate(row) for row in rows], request=request)


@router.post("/admin/payment-channels", summary="Create payment channel")
async def admin_create_payment_channel(request: Request, payload: schemas.PaymentChannelWrite, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    item = PaymentChannel(**payload.model_dump())
    db.add(item)
    await db.commit(); await db.refresh(item)
    return success_response("Payment channel dibuat", data=schemas.PaymentChannelRead.model_validate(item), request=request)


@router.put("/admin/payment-channels/{channel_id}", summary="Update payment channel")
async def admin_update_payment_channel(request: Request, channel_id: uuid.UUID, payload: schemas.PaymentChannelWrite, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    item = await db.get(PaymentChannel, channel_id)
    if not item: raise NotFoundException("PAYMENT_CHANNEL_NOT_FOUND", "Payment channel tidak ditemukan")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item)
    return success_response("Payment channel diperbarui", data=schemas.PaymentChannelRead.model_validate(item), request=request)


@router.delete("/admin/payment-channels/{channel_id}", summary="Delete payment channel")
async def admin_delete_payment_channel(request: Request, channel_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    item = await db.get(PaymentChannel, channel_id)
    if not item: raise NotFoundException("PAYMENT_CHANNEL_NOT_FOUND", "Payment channel tidak ditemukan")
    await db.delete(item); await db.commit()
    return success_response("Payment channel dihapus", data={"id": str(channel_id)}, request=request)


@router.post("/admin/orders/{order_id}/confirm-manual-payment", summary="Confirm manual bank transfer payment")
async def confirm_manual_payment(order_id: uuid.UUID, payload: schemas.ManualPaymentConfirmRequest, request: Request, background_tasks: BackgroundTasks, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    order, payment = await PaymentService.confirm_manual_payment(db, order_id, payload, admin.id)
    background_tasks.add_task(deliver_payment_for_order, order.id)
    return success_response("Pembayaran transfer manual berhasil dikonfirmasi", data={"order": schemas.OrderRead.model_validate(order), "payment": schemas.PaymentRead.model_validate(payment)}, request=request)


@router.post("/payments/orders/{order_id}/manual-proof", status_code=201, summary="Upload manual transfer or static QRIS proof")
async def upload_manual_payment_proof(
    order_id: uuid.UUID,
    request: Request,
    payment_method: str = Form(...),
    transfer_reference: str | None = Form(None),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    payment, proof = await PaymentService.submit_manual_payment_proof(db, order_id, current_user.id, payment_method, transfer_reference, notes, file)
    return success_response("Bukti pembayaran diterima dan menunggu verifikasi", data={"payment": schemas.PaymentRead.model_validate(payment), "proof": schemas.PaymentProofRead.model_validate(proof)}, request=request)


async def _accessible_payment_proof(db: AsyncSession, proof_id: uuid.UUID, user: User, admin_access: bool = False) -> PaymentProof:
    proof = await db.get(PaymentProof, proof_id)
    payment = await db.get(Payment, proof.payment_id) if proof else None
    order = await db.get(Order, payment.order_id) if payment else None
    allowed = bool(order and (order.user_id == user.id or (admin_access and user.role in {"admin", "organizer"})))
    if not proof or not allowed:
        raise NotFoundException("PAYMENT_PROOF_NOT_FOUND", "Bukti pembayaran tidak ditemukan")
    return proof


@router.get("/payments/orders/{order_id}/manual-proofs", summary="List own manual payment proofs")
async def list_manual_payment_proofs(order_id: uuid.UUID, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    order = await db.get(Order, order_id)
    if not order or order.user_id != current_user.id:
        raise NotFoundException("ORDER_NOT_FOUND", "Order tidak ditemukan untuk akun ini")
    rows = (await db.execute(select(PaymentProof).join(Payment, Payment.id == PaymentProof.payment_id).where(Payment.order_id == order_id).order_by(PaymentProof.created_at.desc()))).scalars().all()
    return success_response("Bukti pembayaran ditemukan", data=[schemas.PaymentProofRead.model_validate(row) for row in rows], request=request)


@router.get("/payments/manual-proofs/{proof_id}/download")
async def download_manual_payment_proof(proof_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    proof = await _accessible_payment_proof(db, proof_id, current_user, admin_access=True)
    path = Path(".private_uploads").resolve() / proof.storage_key
    if not path.is_file():
        raise NotFoundException("PAYMENT_PROOF_FILE_NOT_FOUND", "File bukti pembayaran tidak ditemukan")
    return FileResponse(path, media_type=proof.mime_type, filename=proof.original_filename)


@router.get("/admin/orders/{order_id}/manual-proofs", summary="List manual proofs for verification")
async def admin_list_manual_payment_proofs(order_id: uuid.UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db_session)):
    if not await db.get(Order, order_id):
        raise NotFoundException("ORDER_NOT_FOUND", "Order tidak ditemukan")
    rows = (await db.execute(select(PaymentProof).join(Payment, Payment.id == PaymentProof.payment_id).where(Payment.order_id == order_id).order_by(PaymentProof.created_at.desc()))).scalars().all()
    return success_response("Bukti pembayaran untuk verifikasi ditemukan", data=[schemas.PaymentProofRead.model_validate(row) for row in rows], request=request)


@router.get("/payments/doku/direct/methods", summary="List configured DOKU Direct payment methods")
async def doku_direct_methods(request: Request):
    banks = sorted(DokuSnapClient().va_channels())
    settings = get_settings()
    return success_response("Metode DOKU Direct tersedia", data={"virtual_accounts": banks, "qris": bool(settings.DOKU_QRIS_MERCHANT_ID and settings.DOKU_QRIS_TERMINAL_ID)}, request=request)


@router.post("/payments/doku/direct/va", summary="Create DOKU SNAP Virtual Account")
async def create_doku_direct_va(
    request: Request,
    payload: schemas.CreateDokuDirectVARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await PaymentService.create_doku_direct_va(db, payload, current_user.id)
    return success_response("Virtual Account DOKU berhasil dibuat", data=data.model_dump(), request=request)


@router.post("/payments/doku/direct/qris", summary="Generate DOKU SNAP QRIS")
async def create_doku_qris(
    request: Request,
    payload: schemas.CreateDokuQrisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await PaymentService.create_doku_qris(db, payload, current_user.id)
    return success_response("QRIS DOKU berhasil dibuat", data=data.model_dump(), request=request)


@router.post("/payments/doku/snap/direct-debit/bindings", summary="Start DOKU SNAP Direct Debit account binding")
async def create_doku_direct_debit_binding(
    request: Request,
    payload: schemas.CreateDirectDebitBindingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await PaymentService.create_doku_direct_debit_binding(db, payload, current_user.id)
    return success_response("Binding Direct Debit dibuat", data=data.model_dump(), request=request)


@router.post("/payments/doku/snap/direct-debit/payment", summary="Create DOKU SNAP Direct Debit payment")
async def create_doku_direct_debit_payment(
    request: Request,
    payload: schemas.CreateDirectDebitPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await PaymentService.create_doku_direct_debit_payment(db, payload, current_user.id)
    return success_response("Pembayaran Direct Debit dibuat", data=data.model_dump(), request=request)


@router.post("/payments/doku/snap/direct-debit/payment/{payment_id}/otp", summary="Verify DOKU SNAP Direct Debit OTP")
async def verify_doku_direct_debit_otp(
    request: Request,
    payment_id: uuid.UUID,
    payload: schemas.VerifyDirectDebitOtpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await PaymentService.verify_doku_direct_debit_otp(db, payment_id, payload, current_user.id)
    return success_response("OTP Direct Debit diproses", data=data, request=request)


@router.post("/payments/doku/checkout", summary="Create DOKU Checkout payment")
async def create_doku_checkout(
    request: Request,
    payload: schemas.CreateDokuCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data, order = await PaymentService.create_doku_checkout(db, payload, current_user.id)
    message = "DOKU Checkout berhasil dibuat"
    if data.already_paid and not data.requires_payment:
        message = "Anda sudah melakukan pembayaran"
    return success_response(
        message,
        data=data.model_dump(),
        meta={"order_id": str(order.id), "order_number": order.order_number},
        request=request,
    )


@router.post("/payments/midtrans/checkout", summary="Create Midtrans Snap payment")
async def create_midtrans_checkout(
    request: Request,
    payload: schemas.CreateDokuCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data, order = await PaymentService.create_midtrans_checkout(db, payload, current_user.id)
    message = "Midtrans Snap berhasil dibuat" if data.requires_payment else "Anda sudah melakukan pembayaran"
    return success_response(
        message, data=data.model_dump(),
        meta={"order_id": str(order.id), "order_number": order.order_number}, request=request,
    )


@router.get("/payments/midtrans/return", summary="Midtrans browser return landing")
async def midtrans_browser_return(request: Request):
    return success_response(
        "Kembali dari Midtrans. Periksa status pembayaran melalui order atau invoice.",
        data={"payment_status_source": "midtrans_notification"}, request=request,
    )


@router.get("/payments/doku/return", summary="DOKU browser return landing")
async def doku_browser_return(request: Request):
    """Browser landing only; notification remains the payment source of truth."""
    return success_response(
        "Kembali dari DOKU. Periksa status pembayaran melalui order atau invoice.",
        data={"payment_status_source": "doku_notification"},
        request=request,
    )


@router.get("/payments/doku/snap/direct-debit/binding/return", summary="DOKU SNAP Direct Debit binding return landing")
async def doku_direct_debit_binding_return(request: Request):
    """Browser landing after bank binding; the signed API/callback remains authoritative."""
    return success_response(
        "Kembali dari proses binding Direct Debit. Periksa status binding melalui aplikasi.",
        data={"binding_status_source": "doku_snap_direct_debit"},
        request=request,
    )


@router.get("/payments/doku/snap/e-wallet/authorization/return", summary="DOKU SNAP e-Wallet authorization return landing")
async def doku_e_wallet_authorization_return(request: Request):
    return success_response("Kembali dari otorisasi e-Wallet. Periksa status pembayaran melalui aplikasi.", data={"payment_status_source": "doku_snap_e_wallet_notification"}, request=request)


@router.get("/payments/{payment_id}", summary="Get payment")
async def get_payment(
    request: Request,
    payment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    payment = await PaymentService.get_payment(db, payment_id, current_user.id)
    return success_response(
        "Payment ditemukan",
        data=schemas.PaymentRead.model_validate(payment),
        request=request,
    )


@router.get("/orders/{order_id}", summary="Get order")
async def get_order(
    request: Request,
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    order = await PaymentService.get_order(db, order_id, current_user.id)
    return success_response(
        "Order ditemukan",
        data=schemas.OrderRead.model_validate(order),
        request=request,
    )


@router.get("/payments/registrations/{registration_ref}/invoice", summary="Get invoice by registration")
async def get_invoice(
    request: Request,
    registration_ref: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    invoice = await PaymentService.get_invoice(db, registration_ref, current_user.id)
    return success_response(
        "Invoice ditemukan",
        data=invoice,
        request=request,
    )


@router.get("/payments/me/invoices", summary="Get invoices for current user")
async def get_my_invoices(
    request: Request,
    event_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    invoices = await PaymentService.get_my_invoices(
        db,
        current_user.id,
        event_id,
    )
    return success_response(
        "Daftar invoice peserta ditemukan",
        data=invoices,
        request=request,
    )


async def _payment_report_rows(
    db: AsyncSession,
    event_id: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
    status: str | None,
    channel_code: str | None,
    package_id: uuid.UUID | None,
    provider: str = "doku",
):
    if date_from and date_to and date_from > date_to:
        raise ValidationException("INVALID_REPORT_PERIOD", "date_from tidak boleh sesudah date_to")
    normalized_status = status.strip().lower() if status else None
    if normalized_status and normalized_status not in PAYMENT_STATUSES:
        raise ValidationException("INVALID_PAYMENT_STATUS", "Status pembayaran tidak valid")
    return await PaymentReportingService.rows(
        db,
        event_id=event_id,
        date_from=date_from,
        date_to=date_to,
        status=normalized_status,
        channel_code=channel_code,
        package_id=package_id,
        provider=provider,
    )


@router.get("/admin/reports/payments/midtrans", summary="Midtrans payment and revenue report")
async def admin_midtrans_payment_report(
    request: Request,
    event_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    channel_code: str | None = Query(default=None),
    package_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _payment_report_rows(db, event_id, date_from, date_to, status, channel_code, package_id, "midtrans")
    return success_response(
        "Laporan pembayaran Midtrans berhasil diambil",
        data=PaymentReportingService.build_report(rows, limit=limit, offset=offset),
        meta={"total": len(rows), "limit": limit, "offset": offset}, request=request,
    )


@router.get("/admin/reports/payments/midtrans.csv", summary="Export Midtrans payment report as CSV")
async def admin_midtrans_payment_report_csv(
    event_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    channel_code: str | None = Query(default=None),
    package_id: uuid.UUID | None = Query(default=None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _payment_report_rows(db, event_id, date_from, date_to, status, channel_code, package_id, "midtrans")
    filename = f"iwbif-midtrans-payments-{datetime.now().date().isoformat()}.csv"
    return Response(
        content=PaymentReportingService.csv(rows), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/reports/payments/manual", summary="Manual transfer and static QRIS payment report")
async def admin_manual_payment_report(
    request: Request,
    event_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    channel_code: str | None = Query(default=None),
    package_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    organizer: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _payment_report_rows(db, event_id, date_from, date_to, status, channel_code, package_id, "manual")
    return success_response(
        "Laporan pembayaran manual berhasil diambil",
        data=PaymentReportingService.build_report(rows, limit=limit, offset=offset),
        meta={"total": len(rows), "limit": limit, "offset": offset}, request=request,
    )


@router.get("/admin/reports/payments/manual.csv", summary="Export manual payment report as CSV")
async def admin_manual_payment_report_csv(
    event_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    channel_code: str | None = Query(default=None),
    package_id: uuid.UUID | None = Query(default=None),
    organizer: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _payment_report_rows(db, event_id, date_from, date_to, status, channel_code, package_id, "manual")
    filename = f"iwbif-manual-payments-{datetime.now().date().isoformat()}.csv"
    return Response(content=PaymentReportingService.csv(rows), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/admin/reports/payments", summary="DOKU payment and revenue report")
async def admin_payment_report(
    request: Request,
    event_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    channel_code: str | None = Query(default=None),
    package_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _payment_report_rows(db, event_id, date_from, date_to, status, channel_code, package_id)
    data = PaymentReportingService.build_report(rows, limit=limit, offset=offset)
    return success_response(
        "Laporan pembayaran DOKU berhasil diambil",
        data=data,
        meta={"total": len(rows), "limit": limit, "offset": offset},
        request=request,
    )


@router.get("/admin/reports/payments.csv", summary="Export DOKU payment report as CSV")
async def admin_payment_report_csv(
    event_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    channel_code: str | None = Query(default=None),
    package_id: uuid.UUID | None = Query(default=None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    rows = await _payment_report_rows(db, event_id, date_from, date_to, status, channel_code, package_id)
    filename = f"iwbif-doku-payments-{datetime.now().date().isoformat()}.csv"
    return Response(
        content=PaymentReportingService.csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/webhooks/doku", summary="DOKU payment notification")
async def doku_notification(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    body = await request.body()
    result = await PaymentService.handle_doku_notification(db, body, dict(request.headers))
    return success_response("Notifikasi DOKU diproses", data={"result": result}, request=request)


@router.post("/webhooks/midtrans", summary="Midtrans payment notification")
async def midtrans_notification(request: Request, db: AsyncSession = Depends(get_db_session)):
    body, capture_id = await _capture_webhook(request, db, "midtrans")
    try:
        payload = await _parse_captured_webhook(body, capture_id, db)
        result = await PaymentService.handle_midtrans_notification(db, payload)
        await _complete_webhook_capture(capture_id, db, result)
        return success_response("Notifikasi Midtrans diproses", data={"result": result}, request=request)
    except Exception as exc:
        await _fail_webhook_capture(capture_id, db, exc)
        if isinstance(exc, ValueError):
            raise ValidationException("MIDTRANS_INVALID_PAYLOAD", "Payload notifikasi Midtrans tidak valid") from exc
        raise


@router.post("/webhooks/midtrans/recurring", summary="Midtrans recurring/subscription notification")
async def midtrans_recurring_notification(request: Request, db: AsyncSession = Depends(get_db_session)):
    body, capture_id = await _capture_webhook(request, db, "midtrans_recurring")
    try:
        payload = await _parse_captured_webhook(body, capture_id, db)
        subscription = payload.get("subscription") if isinstance(payload.get("subscription"), dict) else payload
        subscription_id = str(subscription.get("id") or "")
        status = str(subscription.get("status") or "")
        if not subscription_id or not status:
            raise ValidationException(
                "MIDTRANS_RECURRING_INVALID_PAYLOAD",
                "Notification recurring tidak memiliki subscription id/status",
            )
        # Official Subscription notification examples do not contain a
        # signature. This inbox acknowledges and audits without mutating orders.
        result = f"captured:{subscription_id}:{status.lower()}"
        await _complete_webhook_capture(capture_id, db, result)
        return success_response("Notifikasi recurring Midtrans diterima", data={"result": result}, request=request)
    except Exception as exc:
        await _fail_webhook_capture(capture_id, db, exc)
        if isinstance(exc, ValueError):
            raise ValidationException("MIDTRANS_INVALID_PAYLOAD", "Payload notifikasi Midtrans tidak valid") from exc
        raise


@router.post("/webhooks/midtrans/account-linking", summary="Midtrans GoPay account linking notification")
async def midtrans_account_linking_notification(request: Request, db: AsyncSession = Depends(get_db_session)):
    body, capture_id = await _capture_webhook(request, db, "midtrans_account")
    try:
        payload = await _parse_captured_webhook(body, capture_id, db)
        if not verify_pay_account_signature(payload, get_settings().MIDTRANS_SERVER_KEY):
            raise ValidationException(
                "MIDTRANS_ACCOUNT_INVALID_SIGNATURE",
                "Signature notification account linking Midtrans tidak valid",
            )
        account_id = str(payload.get("account_id"))
        account_status = str(payload.get("account_status")).lower()
        result = f"verified:{account_id}:{account_status}"
        await _complete_webhook_capture(capture_id, db, result)
        return success_response("Notifikasi account linking Midtrans diterima", data={"result": result}, request=request)
    except Exception as exc:
        await _fail_webhook_capture(capture_id, db, exc)
        if isinstance(exc, ValueError):
            raise ValidationException("MIDTRANS_INVALID_PAYLOAD", "Payload notifikasi Midtrans tidak valid") from exc
        raise


@router.post("/doku/snap/authorization/v1/access-token/b2b", summary="Issue B2B token for DOKU SNAP callback")
async def doku_snap_merchant_token(request: Request):
    try:
        body = await request.json()
        return JSONResponse(PaymentService.issue_doku_snap_token(body, dict(request.headers)))
    except (ValueError, AppException) as exc:
        message = exc.message if isinstance(exc, AppException) else "Invalid JSON"
        return JSONResponse({"responseCode": "4017300", "responseMessage": message}, status_code=401)


@router.post("/webhooks/doku/snap/va/payment", summary="DOKU SNAP Virtual Account payment notification")
async def doku_snap_va_notification(request: Request, db: AsyncSession = Depends(get_db_session)):
    try:
        body = await request.json()
        response = await PaymentService.handle_doku_snap_va_notification(db, body, dict(request.headers))
        return JSONResponse(response)
    except (ValueError, AppException) as exc:
        await db.rollback()
        message = exc.message if isinstance(exc, AppException) else "Invalid JSON"
        status_code = 404 if getattr(exc, "code", "") in {"DOKU_SNAP_PAYMENT_NOT_FOUND", "DOKU_ORDER_NOT_FOUND"} else 400
        response_code = "4042512" if status_code == 404 else "4002500"
        return JSONResponse({"responseCode": response_code, "responseMessage": message}, status_code=status_code)
    except Exception:
        await db.rollback()
        logger.exception("Unexpected DOKU SNAP VA notification error")
        return JSONResponse({"responseCode": "5002500", "responseMessage": "Internal Server Error"}, status_code=500)


@router.post("/webhooks/doku/snap/direct-debit/payment", summary="DOKU SNAP Direct Debit payment notification")
async def doku_snap_direct_debit_notification(request: Request, db: AsyncSession = Depends(get_db_session)):
    try:
        body = await request.json()
        return JSONResponse(await PaymentService.handle_doku_snap_direct_debit_notification(db, body, dict(request.headers)))
    except (ValueError, AppException) as exc:
        await db.rollback()
        return JSONResponse({"responseCode": "4005400", "responseMessage": exc.message if isinstance(exc, AppException) else "Invalid JSON"}, status_code=400)
    except Exception:
        await db.rollback()
        logger.exception("Unexpected DOKU SNAP Direct Debit notification error")
        return JSONResponse({"responseCode": "5005400", "responseMessage": "Internal Server Error"}, status_code=500)


@router.post("/webhooks/doku/snap/e-wallet/payment", summary="DOKU SNAP e-Wallet payment notification")
async def doku_snap_e_wallet_notification(request: Request, db: AsyncSession = Depends(get_db_session)):
    try:
        body = await request.json()
        return JSONResponse(await PaymentService.handle_doku_snap_direct_debit_notification(db, body, dict(request.headers), e_wallet=True))
    except (ValueError, AppException) as exc:
        await db.rollback()
        return JSONResponse({"responseCode": "4005400", "responseMessage": exc.message if isinstance(exc, AppException) else "Invalid JSON"}, status_code=400)
    except Exception:
        await db.rollback()
        logger.exception("Unexpected DOKU SNAP e-Wallet notification error")
        return JSONResponse({"responseCode": "5005400", "responseMessage": "Internal Server Error"}, status_code=500)
