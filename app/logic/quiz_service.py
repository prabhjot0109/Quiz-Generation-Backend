from __future__ import annotations

import hashlib
import re
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.contracts.quiz import QuizSessionCreateRequest
from app.db.models import (
    Answer,
    DifficultyLevel,
    Question,
    QuestionType,
    QuizSession,
    SessionStatus,
    Source,
)
from app.logic.ai import AIProvider
from app.logic.retrieval import retrieve_chunks
from app.logic.scoring import (
    normalize_answer,
    score_objective_answer,
    update_session_after_answer,
)


MAX_GENERATION_ATTEMPTS = 3


class QuestionGenerationError(RuntimeError):
    """Raised when the service cannot generate a unique question."""


async def create_quiz_session(
    session: AsyncSession,
    payload: QuizSessionCreateRequest,
) -> QuizSession:
    source = await session.get(Source, payload.source_id)
    if not source:
        raise LookupError("Source not found.")
    if source.status.value != "ready":
        raise ValueError("Source is not ready for quiz generation.")
    quiz_session = QuizSession(
        source_id=payload.source_id,
        target_question_count=payload.question_count,
        question_types=[question_type.value for question_type in payload.question_types],
        focus_text=payload.focus_text,
        current_difficulty=DifficultyLevel.medium,
        recent_outcomes=[],
    )
    session.add(quiz_session)
    await session.commit()
    await session.refresh(quiz_session)
    return quiz_session


async def get_session_or_404(session: AsyncSession, session_id: UUID) -> QuizSession:
    stmt = (
        select(QuizSession)
        .where(QuizSession.id == session_id)
        .options(
            selectinload(QuizSession.source).selectinload(Source.chunks),
            selectinload(QuizSession.questions).selectinload(Question.answers),
        )
    )
    result = await session.execute(stmt)
    quiz_session = result.scalar_one_or_none()
    if not quiz_session:
        raise LookupError("Quiz session not found.")
    return quiz_session


async def get_or_generate_next_question(
    session: AsyncSession,
    *,
    quiz_session: QuizSession,
    ai_provider: AIProvider,
) -> Question | None:
    unanswered = next(
        (question for question in quiz_session.questions if not question.answer_submitted),
        None,
    )
    if unanswered:
        return unanswered

    if quiz_session.status == SessionStatus.completed:
        return None
    if quiz_session.generated_count >= quiz_session.target_question_count:
        quiz_session.status = SessionStatus.completed
        await session.commit()
        return None

    question_type_values = quiz_session.question_types or [QuestionType.mcq.value]
    question_type = QuestionType(
        question_type_values[quiz_session.generated_count % len(question_type_values)]
    )
    existing_fingerprints = {
        question.question_fingerprint
        for question in quiz_session.questions
        if question.question_fingerprint
    }
    existing_prompts = [question.prompt for question in quiz_session.questions]

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        chunks = await retrieve_chunks(
            session,
            source=quiz_session.source,
            focus_text=quiz_session.focus_text,
            limit=2,
            offset_seed=quiz_session.generated_count + attempt,
        )
        chunk_refs = [str(chunk.id) for chunk in chunks]
        chunk_text = "\n".join(chunk.content for chunk in chunks)
        generated = await ai_provider.generate_question(
            source_title=quiz_session.source.title,
            chunk_text=chunk_text,
            question_type=question_type,
            difficulty=quiz_session.current_difficulty,
            existing_prompts=existing_prompts,
        )
        fingerprint = build_question_fingerprint(
            question_type=generated.question_type,
            prompt=generated.prompt,
            chunk_refs=chunk_refs,
        )
        if fingerprint in existing_fingerprints:
            continue

        question = Question(
            session_id=quiz_session.id,
            source_id=quiz_session.source_id,
            position=quiz_session.generated_count + 1,
            question_type=generated.question_type,
            difficulty=quiz_session.current_difficulty,
            prompt=generated.prompt,
            options=generated.options,
            correct_answer=generated.correct_answer,
            explanation=generated.explanation,
            chunk_refs=chunk_refs,
            question_fingerprint=fingerprint,
        )
        session.add(question)
        quiz_session.generated_count += 1
        await session.commit()
        await session.refresh(question)
        return question

    raise QuestionGenerationError("Unable to generate a unique question for this session.")


async def submit_answer(
    session: AsyncSession,
    *,
    quiz_session: QuizSession,
    question_id: UUID,
    answer_payload: dict[str, object],
    ai_provider: AIProvider,
) -> Answer:
    question = next((item for item in quiz_session.questions if item.id == question_id), None)
    if not question:
        raise LookupError("Question not found.")
    if question.answer_submitted:
        raise ValueError("Question has already been answered.")

    explanation = question.explanation
    if question.question_type == QuestionType.short_answer:
        chunk_texts = [
            chunk.content
            for chunk in quiz_session.source.chunks
            if str(chunk.id) in question.chunk_refs
        ]
        student_answer = str(answer_payload.get("value", ""))
        evaluation = await ai_provider.evaluate_short_answer(
            question=question,
            student_answer=student_answer,
            source_chunks=chunk_texts,
        )
        is_correct = evaluation.is_correct
        score = evaluation.score
        evaluation_mode = evaluation.evaluation_mode
        feedback = evaluation.feedback
        explanation = evaluation.explanation
        normalized = normalize_answer(student_answer)
    else:
        is_correct, score, evaluation_mode = score_objective_answer(question, answer_payload)
        normalized = normalize_answer(
            str(answer_payload.get("value") or answer_payload.get("choice_id") or "")
        )
        feedback = "Correct answer." if is_correct else "Incorrect answer."

    answer = Answer(
        session_id=quiz_session.id,
        question_id=question.id,
        submitted_answer=cast(dict[str, object], answer_payload),
        normalized_answer=normalized,
        is_correct=is_correct,
        score=score,
        evaluation_mode=evaluation_mode,
        feedback=feedback,
        explanation=explanation,
    )
    question.answer_submitted = True
    session.add(answer)
    update_session_after_answer(quiz_session, is_correct, score)
    await session.commit()
    await session.refresh(answer)
    return answer


def build_question_fingerprint(
    *,
    question_type: QuestionType,
    prompt: str,
    chunk_refs: list[str],
) -> str:
    normalized_prompt = re.sub(r"\s+", " ", prompt.lower()).strip()
    fingerprint_source = "|".join(
        [question_type.value, normalized_prompt, ",".join(sorted(chunk_refs))]
    )
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
