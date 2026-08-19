import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import get_settings
from app.core.python_compat import validate_python_version
from app.core.database import init_db
from app.middleware.error_handler import add_exception_handlers
from app.middleware.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    validate_python_version()
    settings = get_settings()
    app = FastAPI(
        title="IWBIF 2026 Event Portal API",
        debug=settings.APP_DEBUG,
        version="1.0.0",
    )

    if settings.CORS_ENABLED:
        allowed_origins = [
            origin.strip()
            for origin in settings.FRONTEND_URL.split(",")
            if origin.strip()
        ]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    add_exception_handlers(app)

    app.add_middleware(RequestIdMiddleware)

    app.include_router(router, prefix=settings.API_PREFIX)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    app.mount(settings.UPLOAD_URL_PREFIX, StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    @app.on_event("startup")
    async def startup() -> None:
        await init_db()
        logging.getLogger(__name__).info("Application startup completed")

    return app


app = create_app()
