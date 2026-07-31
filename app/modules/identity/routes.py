from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.users.models import User
from app.modules.users import schemas as user_schemas
from app.modules.identity import schemas
from app.modules.users.service import UserService
from app.support.responses import success_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", summary="Get current user")
async def me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return success_response(
        "Data profil berhasil diambil",
        data={"user": user_schemas.UserRead.model_validate(current_user)},
        request=request,
    )


@router.put("/me", summary="Update current user")
async def update_me(
    request: Request,
    payload: user_schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    user = await UserService.update_profile(db, current_user, payload)
    return success_response(
        "Profil berhasil diperbarui",
        data={"user": user},
        request=request,
    )


@router.post("/register", summary="Register account")
async def register(
    request: Request,
    payload: user_schemas.UserCreate,
    db: AsyncSession = Depends(get_db_session),
):
    user, access_token, refresh_token = await UserService.register(db, payload)
    return success_response(
        "Registrasi akun berhasil",
        data={
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        request=request,
    )


@router.post("/login", summary="Login account")
async def login(
    request: Request,
    payload: user_schemas.UserLogin,
    db: AsyncSession = Depends(get_db_session),
):
    user, access_token, refresh_token = await UserService.login(db, payload)
    return success_response(
        "Login berhasil",
        data={
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        request=request,
    )


@router.post("/refresh", summary="Refresh access token")
async def refresh(
    request: Request,
    payload: schemas.RefreshRequest,
):
    access_token, refresh_token = await UserService.refresh(payload.refresh_token)
    return success_response(
        "Token di-refresh",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        request=request,
    )


@router.post("/logout", summary="Logout account")
async def logout(request: Request):
    return success_response("Logout berhasil", data={"revoked": True}, request=request)


@router.post("/forgot-password", summary="Forgot password")
async def forgot_password(
    request: Request,
    payload: schemas.ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    token = await UserService.forgot_password(db, payload.email)
    return success_response(
        "Instruksi reset password telah dikirim",
        data={"email": payload.email, "reset_token": token},
        request=request,
    )


@router.post("/reset-password", summary="Reset password")
async def reset_password(
    request: Request,
    payload: schemas.ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await UserService.reset_password(db, payload.token, payload.password, payload.confirm_password)
    return success_response("Password berhasil diubah", data={"token": payload.token}, request=request)


@router.post("/verify-email", summary="Verify email")
async def verify_email(
    request: Request,
    payload: schemas.VerifyEmailRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await UserService.verify_email(db, payload.token)
    return success_response("Email berhasil diverifikasi", data={"token": payload.token}, request=request)


@router.put("/password", summary="Change password")
async def change_password(
    request: Request,
    payload: user_schemas.ChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    await UserService.change_password(db, current_user, payload)
    return success_response("Password berhasil diubah", data={"changed": True}, request=request)
