from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QuestionOptionSchema(BaseModel):
    id: str
    text: str


class McqCorrectAnswerSchema(BaseModel):
    id: str
    text: str


class McqGeneratedQuestionSchema(BaseModel):
    prompt: str
    options: list[QuestionOptionSchema]
    correct_answer: McqCorrectAnswerSchema
    explanation: str


class TrueFalseCorrectAnswerSchema(BaseModel):
    value: bool


class TrueFalseGeneratedQuestionSchema(BaseModel):
    prompt: str
    options: list[QuestionOptionSchema]
    correct_answer: TrueFalseCorrectAnswerSchema
    explanation: str


class FillBlankCorrectAnswerSchema(BaseModel):
    value: str
    acceptable_answers: list[str] = Field(min_length=1)


class FillBlankGeneratedQuestionSchema(BaseModel):
    prompt: str
    options: None = None
    correct_answer: FillBlankCorrectAnswerSchema
    explanation: str


class ShortAnswerCorrectAnswerSchema(BaseModel):
    keywords: list[str] = Field(min_length=1)
    reference_answer: str


class ShortAnswerGeneratedQuestionSchema(BaseModel):
    prompt: str
    options: None = None
    correct_answer: ShortAnswerCorrectAnswerSchema
    explanation: str


class ShortAnswerEvaluationSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    is_correct: bool
    feedback: str
    explanation: str


def json_schema_for_model(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema
