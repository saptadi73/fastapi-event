from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import ValidationException
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.modules.users import schemas
from app.modules.users.repository import UserRepository


class UserService:
    @staticmethod
    async def get_registration_detail(db: AsyncSession, user_id):
        from app.modules.iwbif.models import DelegatePackage, DelegateRegistrationDetail, ExhibitorRegistration
        from app.modules.participants.models import ParticipantProfile
        from app.modules.payments.models import Order, Payment
        from app.modules.registrations.models import Registration
        from app.modules.store.models import OrderItem

        user = await UserRepository.get_by_id(db, user_id)
        if not user:
            raise ValidationException("USER_NOT_FOUND", "User tidak ditemukan")

        participant = (await db.execute(select(ParticipantProfile).where(ParticipantProfile.user_id == user_id))).scalar_one_or_none()
        registrations = []
        if participant:
            delegate_rows = (await db.execute(
                select(Registration, DelegateRegistrationDetail, DelegatePackage)
                .outerjoin(DelegateRegistrationDetail, DelegateRegistrationDetail.registration_id == Registration.id)
                .outerjoin(DelegatePackage, DelegatePackage.id == DelegateRegistrationDetail.delegate_package_id)
                .where(Registration.participant_id == participant.id)
                .order_by(Registration.id.desc())
            )).all()
            for registration, detail, package in delegate_rows:
                registrations.append({
                    "id": registration.id,
                    "type": "delegate",
                    "event_id": registration.event_id,
                    "status": getattr(registration.status, "value", registration.status),
                    "registration_number": registration.registration_number,
                    "package": {"id": package.id, "code": package.code, "name": package.name, "amount": package.amount, "currency": package.currency} if package else None,
                })

            exhibitor_rows = (await db.execute(select(ExhibitorRegistration).where(ExhibitorRegistration.participant_id == participant.id).order_by(ExhibitorRegistration.id.desc()))).scalars().all()
            registrations.extend({
                "id": row.id,
                "type": "exhibitor",
                "event_id": row.event_id,
                "status": row.status,
                "registration_number": None,
                "package": None,
            } for row in exhibitor_rows)

        orders = (await db.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()))).scalars().all()
        order_data = []
        for order in orders:
            items = (await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
            payment = (await db.execute(select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc()))).scalars().first()
            order_data.append({
                "id": order.id,
                "order_number": order.order_number,
                "registration_id": order.registration_id,
                "status": order.status,
                "subtotal": order.subtotal,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "created_at": order.created_at,
                "payment": {"id": payment.id, "status": payment.transaction_status, "provider": payment.provider, "paid_at": payment.paid_at} if payment else None,
                "items": [{"product_id": item.product_id, "code": item.product_code, "name": item.product_name, "type": item.product_type, "quantity": item.quantity, "unit_price": item.unit_price, "line_total": item.line_total, "currency": item.currency} for item in items],
            })

        selected_types = sorted({row["type"] for row in registrations})
        delegate_rows = [row for row in registrations if row["type"] == "delegate"]
        exhibitor_rows = [row for row in registrations if row["type"] == "exhibitor"]
        complete_delegate_statuses = {"submitted", "under_verification", "verified", "payment_pending", "paid", "confirmed"}
        delegate_status = "belum_terdaftar"
        exhibitor_status = "belum_terdaftar"
        if delegate_rows:
            delegate_status = "lengkap" if any(row["status"] in complete_delegate_statuses for row in delegate_rows) else "belum_lengkap"
        if exhibitor_rows:
            exhibitor_status = "lengkap" if any(row["status"] in {"submitted", "paid", "confirmed"} for row in exhibitor_rows) else "belum_lengkap"
        effective_status = user.registration_status
        if selected_types:
            effective_status = "package_selected"
        if any(order["status"] == "pending" for order in order_data):
            effective_status = "payment_pending"
        if any(order["payment"] and order["payment"]["status"] == "success" for order in order_data):
            effective_status = "paid"
        return {
            "user": schemas.UserRead.model_validate(user),
            "registration_status": effective_status,
            "delegate_status": delegate_status,
            "exhibitor_status": exhibitor_status,
            "selected_types": selected_types,
            "profile": schemas.UserProfileSnapshot.model_validate(participant) if participant else None,
            "registrations": registrations,
            "orders": order_data,
        }
    @staticmethod
    async def register(db: AsyncSession, payload: schemas.UserCreate) -> tuple[schemas.UserRead, str, str]:
        password_hash = hash_password(payload.password)
        user = await UserRepository.create(
            session=db,
            email=payload.email,
            password_hash=password_hash,
            country=payload.country,
            phone=payload.phone,
        )
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return schemas.UserRead.model_validate(user), access_token, refresh_token

    @staticmethod
    async def login(db: AsyncSession, payload: schemas.UserLogin) -> tuple[schemas.UserRead, str, str]:
        user = await UserRepository.get_by_email(db, payload.email)
        if not user:
            raise ValidationException(code="INVALID_CREDENTIAL", message="Email atau password salah")
        if not verify_password(payload.password, user.password_hash):
            raise ValidationException(code="INVALID_CREDENTIAL", message="Email atau password salah")
        await UserRepository.touch_last_login(db, user)
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return schemas.UserRead.model_validate(user), access_token, refresh_token

    @staticmethod
    async def refresh(refresh_token: str) -> tuple[str, str]:
        try:
            from app.core.security import decode_token

            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValidationException(code="INVALID_TOKEN", message="Token bukan refresh token")
            user_id = payload.get("sub")
            access_token = create_access_token(user_id)
            refresh = create_refresh_token(user_id)
            return access_token, refresh
        except Exception as exc:
            raise ValidationException(code="INVALID_TOKEN", message="Refresh token tidak valid") from exc

    @staticmethod
    async def update_profile(db: AsyncSession, user, payload: schemas.UserUpdate) -> schemas.UserRead:
        user = await UserRepository.update_profile(
            session=db,
            user=user,
            full_name=payload.full_name,
            phone=payload.phone,
        )
        return schemas.UserRead.model_validate(user)

    @staticmethod
    async def change_password(db: AsyncSession, user, payload: schemas.ChangePassword) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise ValidationException(code="INVALID_CREDENTIAL", message="Password saat ini tidak sesuai")
        if payload.new_password != payload.confirm_password:
            raise ValidationException(code="PASSWORD_MISMATCH", message="Konfirmasi password tidak cocok")
        if payload.new_password == payload.current_password:
            raise ValidationException(code="WEAK_PASSWORD", message="Password baru harus berbeda dari password lama")

        hashed_password = hash_password(payload.new_password)
        await UserRepository.update_password(session=db, user=user, password_hash=hashed_password)
        return None

    @staticmethod
    async def forgot_password(db: AsyncSession, email: str) -> str:
        user = await UserRepository.get_by_email(db, email)
        if not user:
            # Tetap gunakan pesan yang sama untuk menghindari kebocoran akun.
            return create_access_token("unknown", extra={"type": "forgot_password", "email": email.lower()})
        reset_token = create_access_token(str(user.id), extra={"type": "forgot_password"})
        return reset_token

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, password: str, confirm_password: str) -> bool:
        if password != confirm_password:
            raise ValidationException(code="PASSWORD_MISMATCH", message="Konfirmasi password tidak cocok")
        try:
            from app.core.security import decode_token

            payload = decode_token(token)
            if payload.get("type") != "forgot_password":
                raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid")
            user_id = payload.get("sub")
            if not user_id:
                raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid")
            user = await UserRepository.get_by_id(db, user_id)
            if not user:
                raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid")
            password_hash = hash_password(password)
            await UserRepository.update_password(session=db, user=user, password_hash=password_hash)
            return True
        except ValidationException:
            raise
        except Exception as exc:
            raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid") from exc

    @staticmethod
    async def verify_email(db: AsyncSession, token: str) -> bool:
        try:
            from app.core.security import decode_token

            payload = decode_token(token)
            if payload.get("type") != "email_verification":
                raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid")
            user_id = payload.get("sub")
            if not user_id:
                raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid")
            user = await UserRepository.get_by_id(db, user_id)
            if not user:
                raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid")
            if user.is_email_verified:
                return True
            await UserRepository.verify_email(session=db, user=user)
            return True
        except ValidationException:
            raise
        except Exception as exc:
            raise ValidationException(code="INVALID_TOKEN", message="Token tidak valid") from exc
