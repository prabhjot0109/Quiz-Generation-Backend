from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Source, SourceChunk, SourceInputType, SourceStatus
from app.services.chunking import normalize_text, split_into_chunks
from app.services.pdf import extract_pdf_text


@dataclass(slots=True)
class SourcePayload:
    title: str
    input_type: SourceInputType
    raw_text: str | None = None
    pdf_bytes: bytes | None = None
    original_filename: str | None = None


async def create_source(session: AsyncSession, payload: SourcePayload) -> Source:
    source = Source(
        title=payload.title,
        input_type=payload.input_type,
        status=SourceStatus.processing,
        original_filename=payload.original_filename,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def process_source_async(
    session_factory: async_sessionmaker[AsyncSession],
    source_id: UUID,
    payload: SourcePayload,
) -> None:
    async with session_factory() as session:
        source = await session.get(Source, source_id)
        if not source:
            return
        try:
            if payload.input_type == SourceInputType.text:
                extracted_text = normalize_text(payload.raw_text or "")
            else:
                extracted_text = await asyncio.to_thread(extract_pdf_text, payload.pdf_bytes or b"")
                extracted_text = normalize_text(extracted_text)

            if not extracted_text:
                raise ValueError("No extractable text was found in the provided source.")

            chunks = await asyncio.to_thread(split_into_chunks, extracted_text)
            await session.execute(delete(SourceChunk).where(SourceChunk.source_id == source.id))
            for chunk in chunks:
                session.add(
                    SourceChunk(
                        source_id=source.id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        metadata_json={
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                        },
                        search_document=chunk.content,
                    )
                )
            source.status = SourceStatus.ready
            source.extracted_text = extracted_text
            source.summary = extracted_text[:400]
            source.error_message = None
            await session.commit()
        except Exception as exc:
            source.status = SourceStatus.failed
            source.error_message = str(exc)
            await session.commit()


async def get_source_or_404(session: AsyncSession, source_id: UUID) -> Source:
    source = await session.get(Source, source_id)
    if not source:
        raise LookupError("Source not found.")
    return source


async def fetch_source_detail(session: AsyncSession, source_id: UUID) -> tuple[Source, int]:
    source = await get_source_or_404(session, source_id)
    count_result = await session.execute(
        select(func.count(SourceChunk.id)).where(SourceChunk.source_id == source.id)
    )
    chunk_count = int(count_result.scalar_one())
    return source, chunk_count
