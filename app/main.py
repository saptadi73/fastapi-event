import logging

from fastapi import FastAPI
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
        title="ASEAN AI Event Portal API",
        debug=settings.APP_DEBUG,
        version="1.0.0",
    )

    add_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(router, prefix=settings.API_PREFIX)

    @app.on_event("startup")
    async def startup() -> None:
        await init_db()
        logging.getLogger(__name__).info("Application startup completed")

    return app


app = create_app()
