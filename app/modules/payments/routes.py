import logging
import uuid
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.users.models import User
from app.support.responses import success_response
from app.modules.payments import schemas
from app.modules.payments.service import PaymentService
from app.modules.payments.doku_snap import DokuSnapClient
from app.core.exceptions import AppException

router = APIRouter(tags=["payments"])
logger = logging.getLogger(__name__)


@router.get("/payments/doku/direct/methods", summary="List configured DOKU Direct payment methods")
async def doku_direct_methods(request: Request):
    banks = sorted(DokuSnapClient().va_channels())
    return success_response("Metode DOKU Direct tersedia", data={"virtual_accounts": banks, "qris": False}, request=request)


@router.post("/payments/doku/direct/va", summary="Create DOKU SNAP Virtual Account")
async def create_doku_direct_va(
    request: Request,
    payload: schemas.CreateDokuDirectVARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await PaymentService.create_doku_direct_va(db, payload, current_user.id)
    return success_response("Virtual Account DOKU berhasil dibuat", data=data.model_dump(), request=request)


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


@router.post("/webhooks/doku", summary="DOKU payment notification")
async def doku_notification(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    body = await request.body()
    result = await PaymentService.handle_doku_notification(db, body, dict(request.headers))
    return success_response("Notifikasi DOKU diproses", data={"result": result}, request=request)


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
