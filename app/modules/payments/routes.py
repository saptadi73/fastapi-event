import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.users.models import User
from app.support.responses import success_response
from app.modules.payments import schemas
from app.modules.payments.service import PaymentService

router = APIRouter(tags=["payments"])


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
    payment_id,
    db: AsyncSession = Depends(get_db_session),
):
    payment = await PaymentService.get_payment(db, payment_id)
    return success_response(
        "Payment ditemukan",
        data=schemas.PaymentRead.model_validate(payment),
        request=request,
    )


@router.get("/orders/{order_id}", summary="Get order")
async def get_order(
    request: Request,
    order_id,
    db: AsyncSession = Depends(get_db_session),
):
    order = await PaymentService.get_order(db, order_id)
    return success_response(
        "Order ditemukan",
        data=schemas.OrderRead.model_validate(order),
        request=request,
    )


@router.get("/payments/registrations/{registration_ref}/invoice", summary="Get invoice by registration")
async def get_invoice(
    request: Request,
    registration_ref: str,
    db: AsyncSession = Depends(get_db_session),
):
    invoice = await PaymentService.get_invoice(db, registration_ref)
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
