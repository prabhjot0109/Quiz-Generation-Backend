from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.logic.ai import AIProvider


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db.session_factory() as session:
        yield session


def get_ai_provider(request: Request) -> AIProvider:
    return request.app.state.ai_provider
