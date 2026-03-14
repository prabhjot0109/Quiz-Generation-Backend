from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import SourceInputType, SourceStatus


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    input_type: SourceInputType
    status: SourceStatus
    original_filename: str | None = None
    summary: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class SourceChunkResponse(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    metadata: dict[str, object]


class SourceDetailResponse(SourceResponse):
    chunk_count: int
    chunks: list[SourceChunkResponse]
