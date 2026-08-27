import csv
import io
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iwbif.models import DelegatePackage, DelegateRegistrationDetail
from app.modules.participants.models import ParticipantProfile
from app.modules.payments.models import Order, Payment
from app.modules.store.models import OrderItem, Product
from app.modules.users.models import User


def _value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _metadata_package_id(product: Product | None) -> UUID | None:
    if not product or not product.metadata_json or not product.metadata_json.get("delegate_package_id"):
        return None
    try:
        return UUID(str(product.metadata_json["delegate_package_id"]))
    except (TypeError, ValueError):
        return None


class ParticipantReportingService:
    @staticmethod
    async def rows(
        db: AsyncSession,
        *,
        event_id: UUID | None = None,
        package_id: UUID | None = None,
        payment_status: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        participant_stmt = (
            select(ParticipantProfile, User)
            .join(User, User.id == ParticipantProfile.user_id)
            .where(User.role == "participant")
            .order_by(ParticipantProfile.created_at.asc(), ParticipantProfile.id.asc())
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            participant_stmt = participant_stmt.where(or_(
                ParticipantProfile.full_name.ilike(term),
                ParticipantProfile.organization_name.ilike(term),
                User.email.ilike(term),
            ))
        participant_rows = (await db.execute(participant_stmt)).all()
        if not participant_rows:
            return []

        user_ids = [user.id for _, user in participant_rows]
        orders = (await db.execute(
            select(Order).where(Order.user_id.in_(user_ids)).order_by(Order.created_at.asc(), Order.id.asc())
        )).scalars().all()
        order_ids = [order.id for order in orders]

        items_by_order: dict[UUID, list[tuple[OrderItem, Product | None]]] = defaultdict(list)
        payments_by_order: dict[UUID, Payment] = {}
        if order_ids:
            item_rows = (await db.execute(
                select(OrderItem, Product)
                .outerjoin(Product, Product.id == OrderItem.product_id)
                .where(OrderItem.order_id.in_(order_ids))
                .order_by(OrderItem.id.asc())
            )).all()
            for item, product in item_rows:
                items_by_order[item.order_id].append((item, product))

            payments = (await db.execute(
                select(Payment)
                .where(Payment.order_id.in_(order_ids), Payment.deleted_at.is_(None))
                .order_by(Payment.order_id, Payment.created_at.desc(), Payment.id.desc())
            )).scalars().all()
            for payment in payments:
                payments_by_order.setdefault(payment.order_id, payment)

        registration_ids = [order.registration_id for order in orders if order.registration_id]
        direct_packages: dict[UUID, DelegatePackage] = {}
        if registration_ids:
            direct_rows = (await db.execute(
                select(DelegateRegistrationDetail.registration_id, DelegatePackage)
                .join(DelegatePackage, DelegatePackage.id == DelegateRegistrationDetail.delegate_package_id)
                .where(DelegateRegistrationDetail.registration_id.in_(registration_ids))
            )).all()
            direct_packages = {registration_id: package for registration_id, package in direct_rows}

        package_ids = {
            metadata_package_id
            for rows in items_by_order.values()
            for _, product in rows
            if (metadata_package_id := _metadata_package_id(product))
        }
        product_event_ids = {
            product.event_id
            for rows in items_by_order.values()
            for _, product in rows
            if product and product.product_type == "delegate"
        }
        package_query = select(DelegatePackage)
        if package_ids or product_event_ids:
            package_query = package_query.where(or_(
                DelegatePackage.id.in_(package_ids),
                DelegatePackage.event_id.in_(product_event_ids),
            ))
            packages = (await db.execute(package_query)).scalars().all()
        else:
            packages = []
        packages_by_id = {package.id: package for package in packages}
        packages_by_event_code = {(package.event_id, package.code): package for package in packages}

        orders_by_user: dict[UUID, list[Order]] = defaultdict(list)
        for order in orders:
            orders_by_user[order.user_id].append(order)

        result = []
        normalized_status = payment_status.strip().lower() if payment_status else None
        for participant, user in participant_rows:
            purchases = []
            for order in orders_by_user.get(user.id, []):
                payment = payments_by_order.get(order.id)
                payment_state = payment.transaction_status if payment else None
                item_rows = items_by_order.get(order.id, [])
                if item_rows:
                    for item, product in item_rows:
                        package = None
                        metadata_package_id = _metadata_package_id(product)
                        if metadata_package_id:
                            package = packages_by_id.get(metadata_package_id)
                        if not package and product and product.product_type == "delegate":
                            package_code = product.code.removeprefix("DELEGATE_")
                            package = packages_by_event_code.get((product.event_id, package_code))
                        purchase_event_id = product.event_id if product else (package.event_id if package else None)
                        record = ParticipantReportingService._purchase(order, payment, item, package, purchase_event_id)
                        if ParticipantReportingService._matches(record, event_id, package_id, normalized_status):
                            purchases.append(record)
                elif order.registration_id and order.registration_id in direct_packages:
                    package = direct_packages[order.registration_id]
                    record = ParticipantReportingService._purchase(order, payment, None, package, package.event_id)
                    if ParticipantReportingService._matches(record, event_id, package_id, normalized_status):
                        purchases.append(record)

            if purchases or not any((event_id, package_id, normalized_status)):
                result.append({
                    "participant_id": str(participant.id),
                    "user_id": str(user.id),
                    "full_name": participant.full_name,
                    "email": user.email,
                    "phone": user.phone,
                    "country": user.country,
                    "organization_name": participant.organization_name,
                    "registration_status": user.registration_status,
                    "packages": purchases,
                })
        return result

    @staticmethod
    def _matches(record: dict, event_id: UUID | None, package_id: UUID | None, payment_status: str | None) -> bool:
        return (
            (not event_id or record["event_id"] == str(event_id))
            and (not package_id or record["package_id"] == str(package_id))
            and (not payment_status or record["payment_status"] == payment_status)
        )

    @staticmethod
    def _purchase(order, payment, item, package, event_id) -> dict:
        quantity = item.quantity if item else 1
        unit_price = item.unit_price if item else order.total_amount
        line_total = item.line_total if item else order.total_amount
        return {
            "event_id": str(event_id) if event_id else None,
            "package_id": str(package.id) if package else None,
            "package_code": package.code if package else (item.product_code if item else None),
            "package_name": package.name if package else (item.product_name if item else None),
            "package_type": item.product_type if item else "delegate",
            "quantity": quantity,
            "unit_price": _value(unit_price),
            "line_total": _value(line_total),
            "currency": item.currency if item else order.currency,
            "order_id": str(order.id),
            "order_number": order.order_number,
            "order_status": order.status,
            "payment_id": str(payment.id) if payment else None,
            "payment_status": payment.transaction_status if payment else None,
            "payment_provider": payment.provider if payment else None,
            "paid_at": payment.paid_at.isoformat() if payment and payment.paid_at else None,
        }

    @staticmethod
    def csv(rows: list[dict]) -> str:
        output = io.StringIO(newline="")
        columns = [
            "participant_id", "full_name", "email", "phone", "country", "organization_name",
            "event_id", "package_id", "package_code", "package_name", "package_type", "quantity",
            "unit_price", "line_total", "currency", "order_id", "order_number", "order_status",
            "payment_id", "payment_status", "payment_provider", "paid_at",
        ]
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for participant in rows:
            common = {key: participant.get(key) for key in columns if key in participant}
            if participant["packages"]:
                for package in participant["packages"]:
                    writer.writerow({**common, **package})
            else:
                writer.writerow(common)
        return output.getvalue()
