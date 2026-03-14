from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


@pytest.fixture
async def client(tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    settings = Settings.model_validate(
        {
            "ENVIRONMENT": "test",
            "DATABASE_URL": database_url,
            "GEMINI_API_KEY": None,
        }
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
            yield test_client
        async with app.state.db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)


async def wait_for_source_ready(client: AsyncClient, source_id: str) -> dict:
    for _ in range(20):
        response = await client.get(f"/v1/sources/{source_id}")
        data = response.json()
        if data["status"] in {"ready", "failed"}:
            return data
        await asyncio.sleep(0.05)
    raise AssertionError("Source did not finish processing in time.")
