from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceChunk


async def retrieve_chunks(
    session: AsyncSession,
    *,
    source: Source,
    focus_text: str | None,
    limit: int = 2,
    offset_seed: int = 0,
) -> list[SourceChunk]:
    if not source.chunks:
        return []

    if focus_text:
        if session.bind and session.bind.dialect.name == "postgresql":
            stmt = text(
                """
                SELECT id
                FROM source_chunks
                WHERE source_id = :source_id
                  AND to_tsvector('english', search_document)
                      @@ plainto_tsquery('english', :query)
                ORDER BY ts_rank_cd(
                  to_tsvector('english', search_document),
                  plainto_tsquery('english', :query)
                ) DESC, chunk_index ASC
                LIMIT :limit
                """
            )
            rows = await session.execute(
                stmt,
                {"source_id": str(source.id), "query": focus_text, "limit": limit},
            )
            ids = [row[0] for row in rows.fetchall()]
            if ids:
                chunk_stmt = (
                    select(SourceChunk)
                    .where(SourceChunk.id.in_(ids))
                    .order_by(SourceChunk.chunk_index.asc())
                )
                result = await session.execute(chunk_stmt)
                return list(result.scalars().all())

        tokens = [token.strip() for token in focus_text.split() if token.strip()]
        stmt = select(SourceChunk).where(SourceChunk.source_id == source.id)
        for token in tokens[:4]:
            stmt = stmt.where(func.lower(SourceChunk.search_document).contains(token.lower()))
        stmt = stmt.order_by(SourceChunk.chunk_index.asc()).limit(limit)
        result = await session.execute(stmt)
        found = list(result.scalars().all())
        if found:
            return found

    ordered = sorted(source.chunks, key=lambda chunk: chunk.chunk_index)
    start = offset_seed % len(ordered)
    selected = ordered[start : start + limit]
    if len(selected) < limit:
        selected.extend(ordered[: limit - len(selected)])
    return selected
