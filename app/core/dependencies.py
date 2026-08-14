from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Header, HTTPException, status

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.users.repository import UserRepository
from app.modules.users.models import User
from app.modules.users.schemas import UserRead


async def get_db_session() -> AsyncSession:
    async for session in get_db():
        yield session


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user = await UserRepository.get_by_id(db, payload.get("sub"))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    return user


async def get_current_user_payload(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    return decode_token(token)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {"admin", "organizer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organizer role required")
    return current_user
