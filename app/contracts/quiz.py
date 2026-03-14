from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import DifficultyLevel, QuestionType, SessionStatus


class QuizSessionCreateRequest(BaseModel):
    source_id: UUID
    question_count: int = Field(default=5, ge=1, le=20)
    question_types: list[QuestionType] = Field(
        default_factory=lambda: [
            QuestionType.mcq,
            QuestionType.true_false,
            QuestionType.fill_blank,
            QuestionType.short_answer,
        ]
    )
    focus_text: str | None = None


class QuizSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    status: SessionStatus
    current_difficulty: DifficultyLevel
    target_question_count: int
    answered_count: int
    generated_count: int
    correct_count: int
    incorrect_count: int
    last_score: float | None
    question_types: list[str]
    recent_outcomes: list[bool]
    focus_text: str | None
    created_at: datetime
    updated_at: datetime


class QuestionPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    source_id: UUID
    position: int
    question_type: QuestionType
    difficulty: DifficultyLevel
    prompt: str
    options: list[dict[str, Any]] | None
    explanation: str | None
    chunk_refs: list[str]
    answer_submitted: bool
    created_at: datetime
    updated_at: datetime


class NextQuestionResponse(BaseModel):
    completed: bool = False
    question: QuestionPayload | None = None


class AnswerSubmissionRequest(BaseModel):
    answer: dict[str, Any]


class AnswerResponse(BaseModel):
    question_id: UUID
    is_correct: bool
    score: float
    feedback: str | None = None
    explanation: str | None = None
    evaluation_mode: str
    next_difficulty: DifficultyLevel
    session_completed: bool
