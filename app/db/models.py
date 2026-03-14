from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, Uuid, func
from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class SourceInputType(str, enum.Enum):
    text = "text"
    pdf = "pdf"


class SourceStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class DifficultyLevel(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    true_false = "true_false"
    fill_blank = "fill_blank"
    short_answer = "short_answer"


class SessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"


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
        back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )


class SourceChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        Index("ix_source_chunks_source_id_chunk_index", "source_id", "chunk_index"),
    )

    source_id: Mapped[Any] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    search_document: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped["Source"] = relationship(back_populates="chunks")


class QuizSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quiz_sessions"

    source_id: Mapped[Any] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.active
    )
    current_difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel), nullable=False, default=DifficultyLevel.medium
    )
    target_question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    answered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_score: Mapped[float | None] = mapped_column(Float)
    question_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recent_outcomes: Mapped[list[bool]] = mapped_column(JSON, nullable=False, default=list)
    focus_text: Mapped[str | None] = mapped_column(Text)

    source: Mapped["Source"] = relationship(back_populates="quiz_sessions")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    session_id: Mapped[Any] = mapped_column(
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Any] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(Enum(DifficultyLevel), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    correct_answer: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    chunk_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answer_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    session: Mapped["QuizSession"] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", lazy="selectin"
    )


class Answer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answers"

    session_id: Mapped[Any] = mapped_column(
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[Any] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    submitted_answer: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    normalized_answer: Mapped[str | None] = mapped_column(String(512))
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)

    question: Mapped["Question"] = relationship(back_populates="answers")
