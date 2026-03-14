from __future__ import annotations

import pytest

from app.core.config import Settings
from app.db.models import DifficultyLevel, QuestionType
from app.logic.ai import GeminiAIProvider, StructuredOutputError


class StubGeminiProvider(GeminiAIProvider):
    def __init__(self, responses: list[str], *, retries: int = 1) -> None:
        settings = Settings.model_validate(
            {
                "DATABASE_URL": "sqlite+aiosqlite:///unused.db",
                "GEMINI_API_KEY": "test-key",
                "AI_MAX_RETRIES": retries,
            }
        )
        super().__init__(settings)
        self._responses = iter(responses)

    async def _request_json_text(self, prompt: str, schema_model: type):  # type: ignore[override]
        return next(self._responses)


async def test_gemini_provider_accepts_valid_structured_json() -> None:
    provider = StubGeminiProvider(
        [
            """
            {
              "prompt": "True or false: Adaptive quizzes change over time.",
              "options": [{"id": "true", "text": "True"}, {"id": "false", "text": "False"}],
              "correct_answer": {"value": true},
              "explanation": "Adaptive quizzes change over time."
            }
            """
        ]
    )

    question = await provider.generate_question(
        source_title="Adaptive Learning",
        chunk_text="Adaptive quizzes change over time.",
        question_type=QuestionType.true_false,
        difficulty=DifficultyLevel.medium,
    )

    assert question.prompt.startswith("True or false:")
    assert question.correct_answer["value"] is True


async def test_gemini_provider_retries_invalid_json_before_failing() -> None:
    provider = StubGeminiProvider(
        [
            '{"prompt": "bad payload"}',
            """
            {
              "prompt": "Fill in the blank: Adaptive ____ improve retention.",
              "options": null,
              "correct_answer": {
                "value": "quizzes",
                "acceptable_answers": ["quizzes"]
              },
              "explanation": "Adaptive quizzes improve retention."
            }
            """,
        ],
        retries=1,
    )

    question = await provider.generate_question(
        source_title="Adaptive Learning",
        chunk_text="Adaptive quizzes improve retention.",
        question_type=QuestionType.fill_blank,
        difficulty=DifficultyLevel.medium,
    )

    assert question.correct_answer["value"] == "quizzes"


async def test_gemini_provider_raises_on_repeated_invalid_payloads() -> None:
    provider = StubGeminiProvider(['{"prompt": "still bad"}'], retries=0)

    with pytest.raises(StructuredOutputError):
        await provider.generate_question(
            source_title="Adaptive Learning",
            chunk_text="Adaptive quizzes improve retention.",
            question_type=QuestionType.fill_blank,
            difficulty=DifficultyLevel.medium,
        )
