import enum
from typing import Any

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


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
    question_types: Mapped[list[str]] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
    recent_outcomes: Mapped[list[bool]] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
    focus_text: Mapped[str | None] = mapped_column(Text)

    source: Mapped["Source"] = relationship(back_populates="quiz_sessions", lazy="selectin")
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
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
    correct_answer: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
    explanation: Mapped[str | None] = mapped_column(Text)
    chunk_refs: Mapped[list[str]] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
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
    submitted_answer: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSONB, "postgresql"))
    normalized_answer: Mapped[str | None] = mapped_column(String(512))
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)

    question: Mapped["Question"] = relationship(back_populates="answers")


from app.models.source import Source  # noqa: E402
