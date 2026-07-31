from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.modules.users import schemas
from app.modules.users.repository import UserRepository


class UserService:
    @staticmethod
    async def register(db: AsyncSession, payload: schemas.UserCreate) -> tuple[schemas.UserRead, str, str]:
        password_hash = hash_password(payload.password)
        user = await UserRepository.create(
            session=db,
            email=payload.email,
            password_hash=password_hash,
            full_name=payload.full_name,
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
