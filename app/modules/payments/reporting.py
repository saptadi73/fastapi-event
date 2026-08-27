import csv
import io
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.events.models import Event
from app.modules.iwbif.models import DelegatePackage, DelegateRegistrationDetail
from app.modules.payments.models import Order, Payment, PaymentProof, PaymentStatus
from app.modules.registrations.models import Registration
from app.modules.store.models import OrderItem, Product


PAYMENT_STATUSES = {
    PaymentStatus.CREATED,
    PaymentStatus.PENDING,
    PaymentStatus.SUCCESS,
    PaymentStatus.FAILED,
    PaymentStatus.EXPIRED,
    PaymentStatus.REFUNDED,
}


def _money(value: Any) -> float:
    return float(value or 0)


class PaymentReportingService:
    @staticmethod
    async def rows(
        session: AsyncSession,
        *,
        event_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        status: str | None = None,
        channel_code: str | None = None,
        package_id: UUID | None = None,
        provider: str = "doku",
    ) -> list[dict[str, Any]]:
        effective_at = func.coalesce(Payment.paid_at, Payment.created_at)
        store_product = aliased(Product)
        store_package = aliased(DelegatePackage)
        purchased_event_id = (
            select(store_product.event_id)
            .select_from(OrderItem)
            .join(store_product, store_product.id == OrderItem.product_id)
            .where(OrderItem.order_id == Order.id, store_product.product_type == "delegate")
            .order_by(OrderItem.id)
            .limit(1)
            .correlate(Order)
            .scalar_subquery()
        )
        purchased_package_id = (
            select(store_package.id)
            .select_from(OrderItem)
            .join(store_product, store_product.id == OrderItem.product_id)
            .join(
                store_package,
                and_(
                    store_package.event_id == store_product.event_id,
                    store_product.code == literal("DELEGATE_") + store_package.code,
                ),
            )
            .where(OrderItem.order_id == Order.id, store_product.product_type == "delegate")
            .order_by(OrderItem.id)
            .limit(1)
            .correlate(Order)
            .scalar_subquery()
        )
        effective_event_id = func.coalesce(Registration.event_id, purchased_event_id)
        effective_package_id = func.coalesce(DelegateRegistrationDetail.delegate_package_id, purchased_package_id)
        stmt = (
            select(
                Payment.id.label("payment_id"),
                Payment.provider,
                Payment.created_at,
                Payment.paid_at,
                Payment.transaction_status,
                Payment.payment_type,
                Payment.channel_code,
                Payment.gross_amount,
                Payment.currency,
                Payment.provider_transaction_id,
                Payment.provider_order_id,
                Payment.provider_reference_no,
                Payment.virtual_account_no,
                Order.id.label("order_id"),
                Order.order_number,
                Order.status.label("order_status"),
                Registration.id.label("registration_id"),
                Registration.registration_number,
                effective_event_id.label("event_id"),
                Event.name.label("event_name"),
                DelegateRegistrationDetail.full_name.label("customer_name"),
                DelegateRegistrationDetail.email.label("customer_email"),
                DelegatePackage.id.label("package_id"),
                DelegatePackage.code.label("package_code"),
                DelegatePackage.name.label("package_name"),
            )
            .join(Order, Payment.order_id == Order.id)
            # Store-first payments can complete before a registration exists.
            .outerjoin(Registration, Order.registration_id == Registration.id)
            .outerjoin(Event, effective_event_id == Event.id)
            .outerjoin(
                DelegateRegistrationDetail,
                DelegateRegistrationDetail.registration_id == Registration.id,
            )
            .outerjoin(
                DelegatePackage,
                DelegatePackage.id == effective_package_id,
            )
            .order_by(effective_at.desc(), Payment.id.desc())
        )
        if provider == "doku":
            stmt = stmt.where(Payment.provider.like("doku%"))
        elif provider == "manual":
            stmt = stmt.where(Payment.provider.in_(["manual_transfer", "manual_qr_code"]))
        elif provider:
            stmt = stmt.where(Payment.provider == provider)
        if event_id:
            stmt = stmt.where(effective_event_id == event_id)
        if date_from:
            stmt = stmt.where(effective_at >= date_from)
        if date_to:
            stmt = stmt.where(effective_at <= date_to)
        if status:
            stmt = stmt.where(Payment.transaction_status == status)
        if channel_code:
            stmt = stmt.where(func.upper(Payment.channel_code) == channel_code.strip().upper())
        if package_id:
            stmt = stmt.where(effective_package_id == package_id)

        result = await session.execute(stmt)
        rows = [dict(row._mapping) for row in result.all()]
        payment_ids = [row["payment_id"] for row in rows]
        if not payment_ids:
            return rows
        proofs = (await session.execute(
            select(PaymentProof)
            .where(PaymentProof.payment_id.in_(payment_ids))
            .order_by(PaymentProof.created_at.desc())
        )).scalars().all()
        proofs_by_payment: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
        for proof in proofs:
            proofs_by_payment[proof.payment_id].append({
                "id": proof.id,
                "original_filename": proof.original_filename,
                "mime_type": proof.mime_type,
                "file_size": proof.file_size,
                "notes": proof.notes,
                "uploaded_by": proof.uploaded_by,
                "created_at": proof.created_at,
                "download_url": f"/api/v1/payments/manual-proofs/{proof.id}/download",
            })
        for row in rows:
            row["payment_proofs"] = proofs_by_payment.get(row["payment_id"], [])
            row["payment_proof_count"] = len(row["payment_proofs"])
        return rows

    @staticmethod
    def build_report(rows: list[dict[str, Any]], *, limit: int, offset: int) -> dict[str, Any]:
        by_status: dict[str, dict[str, Any]] = defaultdict(lambda: {"transactions": 0, "amount": 0.0})
        by_channel: dict[str, dict[str, Any]] = defaultdict(lambda: {"transactions": 0, "successful_transactions": 0, "revenue": 0.0})
        by_package: dict[str, dict[str, Any]] = {}
        daily: dict[str, dict[str, Any]] = defaultdict(lambda: {"transactions": 0, "revenue": 0.0})
        successful = pending = failed = expired = 0
        revenue = pending_amount = 0.0

        for row in rows:
            amount = _money(row["gross_amount"])
            payment_status = str(row["transaction_status"])
            channel = row["channel_code"] or row["payment_type"] or "UNKNOWN"
            by_status[payment_status]["transactions"] += 1
            by_status[payment_status]["amount"] += amount
            by_channel[channel]["transactions"] += 1

            if payment_status == PaymentStatus.SUCCESS:
                successful += 1
                revenue += amount
                by_channel[channel]["successful_transactions"] += 1
                by_channel[channel]["revenue"] += amount
                package_key = str(row["package_id"] or "unassigned")
                package = by_package.setdefault(package_key, {
                    "package_id": str(row["package_id"]) if row["package_id"] else None,
                    "package_code": row["package_code"],
                    "package_name": row["package_name"] or "Unassigned",
                    "tickets_sold": 0,
                    "revenue": 0.0,
                })
                package["tickets_sold"] += 1
                package["revenue"] += amount
                paid_at = row["paid_at"] or row["created_at"]
                day = paid_at.date().isoformat()
                daily[day]["transactions"] += 1
                daily[day]["revenue"] += amount
            elif payment_status in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
                pending += 1
                pending_amount += amount
            elif payment_status == PaymentStatus.FAILED:
                failed += 1
            elif payment_status == PaymentStatus.EXPIRED:
                expired += 1

        transactions = [PaymentReportingService.serialize_row(row) for row in rows[offset:offset + limit]]
        currency = next((str(row["currency"]) for row in rows if row["currency"]), "IDR")
        return {
            "summary": {
                "total_transactions": len(rows),
                "successful_transactions": successful,
                "pending_transactions": pending,
                "failed_transactions": failed,
                "expired_transactions": expired,
                "gross_revenue": round(revenue, 2),
                "pending_amount": round(pending_amount, 2),
                "currency": currency,
            },
            "by_status": [dict(status=key, **value) for key, value in sorted(by_status.items())],
            "by_channel": [dict(channel_code=key, **value) for key, value in sorted(by_channel.items())],
            "by_package": sorted(by_package.values(), key=lambda item: item["revenue"], reverse=True),
            "daily_revenue": [dict(date=key, **value) for key, value in sorted(daily.items())],
            "transactions": transactions,
        }

    @staticmethod
    def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        serialized = {
            key: (
                value.isoformat()
                if isinstance(value, datetime)
                else str(value)
                if isinstance(value, UUID)
                else _money(value)
                if isinstance(value, Decimal)
                else value
            )
            for key, value in row.items()
        }
        if "payment_proofs" in row:
            serialized["payment_proofs"] = [
                PaymentReportingService.serialize_row(proof) for proof in row["payment_proofs"]
            ]
        return serialized

    @staticmethod
    def csv(rows: list[dict[str, Any]]) -> str:
        output = io.StringIO(newline="")
        columns = [
            "payment_id", "created_at", "paid_at", "provider", "transaction_status", "payment_type",
            "channel_code", "gross_amount", "currency", "provider_transaction_id",
            "provider_order_id", "provider_reference_no", "virtual_account_no", "order_id", "order_number",
            "order_status", "registration_id", "registration_number", "event_id", "event_name",
            "customer_name", "customer_email", "package_id", "package_code", "package_name",
            "payment_proof_count", "payment_proof_download_urls",
        ]
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = PaymentReportingService.serialize_row(row)
            serialized["payment_proof_download_urls"] = " | ".join(
                proof["download_url"] for proof in serialized.get("payment_proofs", [])
            )
            writer.writerow(serialized)
        return output.getvalue()
