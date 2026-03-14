from __future__ import annotations

import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.contracts.ai import (
    FillBlankGeneratedQuestionSchema,
    McqGeneratedQuestionSchema,
    ShortAnswerEvaluationSchema,
    ShortAnswerGeneratedQuestionSchema,
    TrueFalseGeneratedQuestionSchema,
    json_schema_for_model,
)
from app.core.config import Settings
from app.db.models import DifficultyLevel, Question, QuestionType


@dataclass(slots=True)
class GeneratedQuestion:
    question_type: QuestionType
    prompt: str
    options: list[dict[str, Any]] | None
    correct_answer: dict[str, Any]
    explanation: str


@dataclass(slots=True)
class ShortAnswerEvaluation:
    score: float
    is_correct: bool
    feedback: str
    explanation: str
    evaluation_mode: str = "ai"


class StructuredOutputError(ValueError):
    """Raised when Gemini returns invalid structured data."""


class AIProvider:
    async def generate_question(
        self,
        *,
        source_title: str,
        chunk_text: str,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        existing_prompts: Sequence[str] = (),
    ) -> GeneratedQuestion:
        raise NotImplementedError

    async def evaluate_short_answer(
        self,
        *,
        question: Question,
        student_answer: str,
        source_chunks: Sequence[str],
    ) -> ShortAnswerEvaluation:
        raise NotImplementedError


class MockAIProvider(AIProvider):
    async def generate_question(
        self,
        *,
        source_title: str,
        chunk_text: str,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        existing_prompts: Sequence[str] = (),
    ) -> GeneratedQuestion:
        sentences = _split_sentences(chunk_text)
        anchor = _choose_anchor(sentences or [chunk_text[:200]], existing_prompts)
        if question_type == QuestionType.mcq:
            return _mock_mcq(anchor, difficulty)
        if question_type == QuestionType.true_false:
            return _mock_true_false(anchor)
        if question_type == QuestionType.fill_blank:
            return _mock_fill_blank(anchor)
        return _mock_short_answer(anchor, source_title, difficulty)

    async def evaluate_short_answer(
        self,
        *,
        question: Question,
        student_answer: str,
        source_chunks: Sequence[str],
    ) -> ShortAnswerEvaluation:
        expected_keywords = question.correct_answer.get("keywords", [])
        normalized = _normalize(student_answer)
        hits = sum(1 for keyword in expected_keywords if _normalize(keyword) in normalized)
        total = max(1, len(expected_keywords))
        score = hits / total
        is_correct = score >= 0.5
        feedback = (
            "Good coverage of the main source concepts."
            if is_correct
            else "The answer misses some of the core ideas from the source."
        )
        return ShortAnswerEvaluation(
            score=round(score, 2),
            is_correct=is_correct,
            feedback=feedback,
            explanation=question.correct_answer.get("reference_answer", ""),
            evaluation_mode="mock_ai",
        )


class GeminiAIProvider(AIProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
        )

    async def generate_question(
        self,
        *,
        source_title: str,
        chunk_text: str,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        existing_prompts: Sequence[str] = (),
    ) -> GeneratedQuestion:
        schema_model = _schema_model_for_question_type(question_type)
        duplicate_guidance = _duplicate_guidance(existing_prompts)
        prompt = (
            "Build one grounded quiz question from the provided source chunk.\n"
            f"Source title: {source_title}\n"
            f"Difficulty: {difficulty.value}\n"
            f"Question type: {question_type.value}\n"
            "Ground every question to the source chunk and keep it self-contained.\n"
            f"{duplicate_guidance}"
            f"Source chunk:\n{chunk_text}"
        )
        payload = await self._generate_structured(prompt, schema_model)
        payload_dict = payload.model_dump()
        return GeneratedQuestion(
            question_type=question_type,
            prompt=payload_dict["prompt"],
            options=payload_dict.get("options"),
            correct_answer=payload_dict["correct_answer"],
            explanation=payload_dict["explanation"],
        )

    async def evaluate_short_answer(
        self,
        *,
        question: Question,
        student_answer: str,
        source_chunks: Sequence[str],
    ) -> ShortAnswerEvaluation:
        prompt = (
            "Evaluate the student's short answer against the grounded quiz question.\n"
            f"Question: {question.prompt}\n"
            f"Expected answer guidance: {json.dumps(question.correct_answer)}\n"
            f"Source context: {' '.join(source_chunks)}\n"
            f"Student answer: {student_answer}"
        )
        payload = await self._generate_structured(prompt, ShortAnswerEvaluationSchema)
        return ShortAnswerEvaluation(
            score=payload.score, # type: ignore
            is_correct=payload.is_correct,
            feedback=payload.feedback,
            explanation=payload.explanation,
            evaluation_mode="gemini",
        )

    async def _generate_structured(
        self,
        prompt: str,
        schema_model: type[BaseModel],
    ) -> BaseModel:
        last_error: Exception | None = None
        for attempt in range(self.settings.ai_max_retries + 1):
            try:
                raw_text = await self._request_json_text(prompt, schema_model)
                return schema_model.model_validate_json(raw_text)
            except (StructuredOutputError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.settings.ai_max_retries:
                    break
        raise StructuredOutputError(
            f"Gemini returned invalid structured output after retries: {last_error}"
        )

    async def _request_json_text(
        self,
        prompt: str,
        schema_model: type[BaseModel],
    ) -> str:
        timeout = httpx.Timeout(self.settings.ai_request_timeout_seconds)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": json_schema_for_model(schema_model),
            },
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self.endpoint,
                params={"key": self.settings.gemini_api_key},
                json=body,
            )
            response.raise_for_status()
        data = response.json()
        text = "".join(
            part.get("text", "")
            for candidate in data.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
        ).strip()
        if not text:
            raise StructuredOutputError("Gemini response did not contain JSON text.")
        return text


def build_ai_provider(settings: Settings) -> AIProvider:
    if settings.gemini_api_key:
        return GeminiAIProvider(settings)
    return MockAIProvider()


def _schema_model_for_question_type(question_type: QuestionType) -> type[BaseModel]:
    if question_type == QuestionType.mcq:
        return McqGeneratedQuestionSchema
    if question_type == QuestionType.true_false:
        return TrueFalseGeneratedQuestionSchema
    if question_type == QuestionType.fill_blank:
        return FillBlankGeneratedQuestionSchema
    return ShortAnswerGeneratedQuestionSchema


def _duplicate_guidance(existing_prompts: Sequence[str]) -> str:
    if not existing_prompts:
        return ""
    preview = "\n".join(f"- {prompt}" for prompt in list(existing_prompts)[-3:])
    return f"Avoid repeating these recent questions or phrasings:\n{preview}\n"


def _split_sentences(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text) if segment.strip()]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", value.lower())).strip()


def _choose_anchor(sentences: Sequence[str], existing_prompts: Sequence[str]) -> str:
    normalized_prompts = [_normalize(prompt) for prompt in existing_prompts]
    for sentence in sentences:
        sentence_key = _normalize(sentence)
        if all(sentence_key not in prompt for prompt in normalized_prompts):
            return sentence
    return sentences[0]


def _mock_mcq(anchor: str, difficulty: DifficultyLevel) -> GeneratedQuestion:
    prompt = f"Which statement best matches this source idea: {anchor[:90]}?"
    correct_text = anchor.strip()
    distractors = [
        f"The source rejects this idea: {correct_text[:80]}",
        f"The topic is unrelated to: {correct_text[:80]}",
        f"The source states the opposite of: {correct_text[:80]}",
    ]
    random.Random(correct_text).shuffle(distractors)
    options = [{"id": "a", "text": correct_text}]
    for index, option in enumerate(distractors[:3], start=1):
        options.append({"id": chr(ord("a") + index), "text": option})
    random.Random(f"{correct_text}-{difficulty.value}").shuffle(options)
    correct_option = next(option for option in options if option["text"] == correct_text)
    return GeneratedQuestion(
        question_type=QuestionType.mcq,
        prompt=prompt,
        options=options,
        correct_answer={"id": correct_option["id"], "text": correct_option["text"]},
        explanation=correct_text,
    )


def _mock_true_false(anchor: str) -> GeneratedQuestion:
    statement = anchor.strip()
    return GeneratedQuestion(
        question_type=QuestionType.true_false,
        prompt=f"True or false: {statement}",
        options=[{"id": "true", "text": "True"}, {"id": "false", "text": "False"}],
        correct_answer={"value": True},
        explanation=statement,
    )


def _mock_fill_blank(anchor: str) -> GeneratedQuestion:
    words = [word for word in re.findall(r"[A-Za-z]{5,}", anchor)]
    answer = max(words, key=len) if words else "concept"
    prompt = re.sub(re.escape(answer), "____", anchor, count=1, flags=re.IGNORECASE)
    return GeneratedQuestion(
        question_type=QuestionType.fill_blank,
        prompt=f"Fill in the blank: {prompt}",
        options=None,
        correct_answer={"value": answer, "acceptable_answers": [answer]},
        explanation=anchor,
    )


def _mock_short_answer(
    anchor: str,
    source_title: str,
    difficulty: DifficultyLevel,
) -> GeneratedQuestion:
    keywords = [word for word in re.findall(r"[A-Za-z]{5,}", anchor)[:4]]
    if not keywords:
        keywords = [source_title.split()[0] if source_title else "topic"]
    focus_phrase = " ".join(anchor.split()[:8])
    prompt = (
        f"In 2-3 sentences, explain this idea from {source_title}: {focus_phrase}"
        if difficulty != DifficultyLevel.easy
        else f"Briefly explain this point from {source_title}: {focus_phrase}"
    )
    return GeneratedQuestion(
        question_type=QuestionType.short_answer,
        prompt=prompt,
        options=None,
        correct_answer={"keywords": keywords, "reference_answer": anchor},
        explanation=anchor,
    )
