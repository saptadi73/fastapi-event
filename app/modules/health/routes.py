from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from starlette.requests import Request
from app.support.responses import success_response
from app.core.dependencies import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health():
    return success_response(message="OK", data={"status": "alive"})


@router.get("/health/database", summary="Database connectivity check")
async def health_database(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        await db.execute(text("SELECT 1"))
        return success_response(
            message="Database connection healthy",
            data={"status": "connected"},
            request=request,
        )
    except Exception as exc:
        return success_response(
            message="Database connection failed",
            data={"status": "disconnected", "error": str(exc)},
            request=request,
        )


@router.get("/health/readiness", summary="Readiness check")
async def health_readiness(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        await db.execute(text("SELECT 1"))
        return success_response(
            message="Service is ready",
            data={"ready": True, "database": "connected"},
            request=request,
        )
    except Exception as exc:
        return success_response(
            message="Service not ready",
            data={"ready": False, "database": "disconnected", "error": str(exc)},
            request=request,
        )
