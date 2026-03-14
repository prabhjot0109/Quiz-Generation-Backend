from __future__ import annotations

import re

from app.db.models import DifficultyLevel, Question, QuestionType, QuizSession, SessionStatus


def normalize_answer(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def score_objective_answer(question: Question, answer_payload: dict[str, object]) -> tuple[bool, float, str]:
    if question.question_type == QuestionType.mcq:
        submitted = str(answer_payload.get("choice_id", "")).strip().lower()
        expected = str(question.correct_answer.get("id", "")).strip().lower()
        is_correct = submitted == expected
        return is_correct, 1.0 if is_correct else 0.0, "deterministic"

    if question.question_type == QuestionType.true_false:
        submitted_raw = str(answer_payload.get("value", "")).strip().lower()
        submitted = submitted_raw in {"true", "1", "yes"}
        expected = bool(question.correct_answer.get("value"))
        is_correct = submitted == expected
        return is_correct, 1.0 if is_correct else 0.0, "deterministic"

    if question.question_type == QuestionType.fill_blank:
        submitted = normalize_answer(str(answer_payload.get("value", "")))
        expected_values = question.correct_answer.get("acceptable_answers") or [
            question.correct_answer.get("value", "")
        ]
        normalized_expected = {normalize_answer(str(value)) for value in expected_values}
        is_correct = submitted in normalized_expected
        return is_correct, 1.0 if is_correct else 0.0, "deterministic"

    raise ValueError("Objective scoring only applies to non-short-answer questions.")


def update_session_after_answer(session: QuizSession, is_correct: bool, score: float) -> None:
    session.answered_count += 1
    session.last_score = score
    if is_correct:
        session.correct_count += 1
    else:
        session.incorrect_count += 1
    outcomes = list(session.recent_outcomes or [])
    outcomes.append(is_correct)
    session.recent_outcomes = outcomes[-3:]
    session.current_difficulty = adjust_difficulty(
        session.current_difficulty, session.recent_outcomes
    )
    if session.answered_count >= session.target_question_count:
        session.status = SessionStatus.completed


def adjust_difficulty(current: DifficultyLevel, recent_outcomes: list[bool]) -> DifficultyLevel:
    if len(recent_outcomes) < 2:
        return current
    if recent_outcomes[-2:] == [True, True]:
        if current == DifficultyLevel.easy:
            return DifficultyLevel.medium
        if current == DifficultyLevel.medium:
            return DifficultyLevel.hard
        return DifficultyLevel.hard
    if recent_outcomes[-2:] == [False, False]:
        if current == DifficultyLevel.hard:
            return DifficultyLevel.medium
        if current == DifficultyLevel.medium:
            return DifficultyLevel.easy
        return DifficultyLevel.easy
    return current
