from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.support.responses import success_response
from app.modules.payments import schemas
from app.modules.payments.service import PaymentService

router = APIRouter(tags=["payments"])


@router.post("/payments/midtrans/create", summary="Create Midtrans transaction")
async def create_midtrans_transaction(
    request: Request,
    payload: schemas.CreateMidtransRequest,
    db: AsyncSession = Depends(get_db_session),
):
    data, order = await PaymentService.create_midtrans_session(db, payload)
    return success_response(
        "Midtrans transaksi berhasil dibuat",
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


@router.post("/webhooks/midtrans", summary="Midtrans webhook")
async def midtrans_webhook(
    request: Request,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
):
    result = await PaymentService.handle_midtrans_webhook(db, payload)
    return success_response("Webhook diproses", data={"result": result}, request=request)

