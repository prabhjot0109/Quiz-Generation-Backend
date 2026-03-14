from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.db.session import DatabaseManager
from app.http.routes import router
from app.logic.ai import build_ai_provider


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = DatabaseManager(app_settings.database_url)
        app.state.db = db
        app.state.ai_provider = build_ai_provider(app_settings)
        try:
            yield
        finally:
            await db.dispose()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
