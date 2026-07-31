from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.constants import ErrorCode
from app.core.exceptions import AppException, ConflictException, NotFoundException, ValidationException
from app.support.responses import fail_response


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(exc, NotFoundException):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ValidationException):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, ConflictException):
            status_code = status.HTTP_409_CONFLICT
        return JSONResponse(
            status_code=status_code,
            content=fail_response(
                message=exc.message,
                errors=[{"field": "", "code": exc.code, "message": exc.message}],
                request=request,
            ),
        )

    @app.exception_handler(ValidationError)
    async def handle_pydantic_validation(request: Request, exc: ValidationError):
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error.get("loc", []))
            errors.append(
                {
                    "field": field,
                    "code": error.get("type", ErrorCode.VALIDATION_ERROR),
                    "message": error.get("msg", "Validation error"),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=fail_response(
                message="Validation failed",
                errors=errors,
                request=request,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=fail_response(
                message="Database constraint violation",
                errors=[{"field": "", "code": ErrorCode.CONFLICT, "message": str(exc.orig)}],
                request=request,
            ),
        )

