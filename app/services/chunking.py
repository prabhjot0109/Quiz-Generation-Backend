from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.config import get_settings


@dataclass(slots=True)
class Chunk:
    chunk_index: int
    content: str
    start_char: int
    end_char: int


def normalize_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_into_chunks(text: str) -> list[Chunk]:
    settings = get_settings()
    normalized = normalize_text(text)
    if not normalized:
        return []

    chunk_size = settings.chunk_size
    overlap = min(settings.chunk_overlap, max(0, chunk_size // 3))
    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        if end < len(normalized):
            last_space = normalized.rfind(" ", start, end)
            if last_space > start + chunk_size // 2:
                end = last_space
        content = normalized[start:end].strip()
        if content:
            chunks.append(
                Chunk(chunk_index=index, content=content, start_char=start, end_char=end)
            )
            index += 1
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks
