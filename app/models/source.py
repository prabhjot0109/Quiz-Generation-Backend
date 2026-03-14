import enum
from typing import Any

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SourceInputType(str, enum.Enum):
    text = "text"
    pdf = "pdf"


class SourceStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    input_type: Mapped[SourceInputType] = mapped_column(Enum(SourceInputType), nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus), nullable=False, default=SourceStatus.pending
    )
    original_filename: Mapped[str | None] = mapped_column(String(255))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    chunks: Mapped[list["SourceChunk"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    quiz_sessions: Mapped[list["QuizSession"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        Index("ix_source_chunks_source_id_chunk_index", "source_id", "chunk_index"),
    )

    source_id: Mapped[Any] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
    search_document: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped["Source"] = relationship(back_populates="chunks")


from app.models.quiz import QuizSession  # noqa: E402
