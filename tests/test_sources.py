from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import wait_for_source_ready


async def test_text_source_ingestion_becomes_ready(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/sources",
        json={
            "title": "Peblo Notes",
            "text": "Adaptive systems adjust difficulty based on learner performance. "
            "Deterministic logic keeps progression transparent.",
        },
    )
    assert response.status_code == 202
    source = response.json()
    detail = await wait_for_source_ready(client, source["id"])

    assert detail["status"] == "ready"
    assert detail["chunk_count"] >= 1
    assert "Adaptive systems adjust difficulty" in detail["summary"]
