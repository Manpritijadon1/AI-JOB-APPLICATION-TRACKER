from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.jobs import router as jobs_router
from app.core.config import Settings, get_settings
from app.core.ai_limits import AIRequestSizeLimitMiddleware
from app.db.session import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    engine = create_database_engine(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_database(engine)
        yield

    application = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    application.state.settings = app_settings
    application.state.db_engine = engine
    application.state.db_session_factory = create_session_factory(engine)
    application.include_router(auth_router)
    application.include_router(jobs_router)
    application.include_router(dashboard_router)
    application.include_router(ai_router)
    application.add_middleware(
        AIRequestSizeLimitMiddleware,
        max_body_bytes=app_settings.ai_max_request_bytes,
    )

    @application.get("/")
    def read_root() -> dict[str, str]:
        return {"message": app_settings.app_name}

    @application.get("/health")
    def read_health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
