from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, status
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.quiz import (
    AnswerResponse,
    AnswerSubmissionRequest,
    NextQuestionResponse,
    QuestionPayload,
    QuizSessionCreateRequest,
    QuizSessionResponse,
)
from app.contracts.source import SourceChunkResponse, SourceDetailResponse, SourceResponse
from app.db.models import SourceInputType
from app.http.dependencies import get_ai_provider, get_db_session
from app.logic.ai import AIProvider, StructuredOutputError
from app.logic.quiz_service import (
    QuestionGenerationError,
    create_quiz_session,
    get_or_generate_next_question,
    get_session_or_404,
    submit_answer,
)
from app.logic.source_service import (
    SourcePayload,
    create_source,
    fetch_source_detail,
    process_source_async,
)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/v1/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["text"],
                    }
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "text": {"type": "string"},
                            "file": {"type": "string", "format": "binary"},
                        },
                    }
                },
            },
        }
    },
)
async def create_source_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> SourceResponse:
    payload = await _parse_source_payload(request)
    source = await create_source(session, payload)
    background_tasks.add_task(
        process_source_async,
        request.app.state.db.session_factory,
        source.id,
        payload,
    )
    return SourceResponse.model_validate(source)


@router.get("/v1/sources/{source_id}", response_model=SourceDetailResponse)
async def get_source_endpoint(
    source_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> SourceDetailResponse:
    try:
        source, chunk_count, chunks = await fetch_source_detail(session, source_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SourceDetailResponse(
        **SourceResponse.model_validate(source).model_dump(),
        chunk_count=chunk_count,
        chunks=[
            SourceChunkResponse(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata=chunk.metadata_json,
            )
            for chunk in chunks
        ],
    )


@router.post(
    "/v1/quiz-sessions", response_model=QuizSessionResponse, status_code=status.HTTP_201_CREATED
)
async def create_quiz_session_endpoint(
    payload: QuizSessionCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> QuizSessionResponse:
    try:
        quiz_session = await create_quiz_session(session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return QuizSessionResponse.model_validate(quiz_session)


@router.get("/v1/quiz-sessions/{session_id}/next-question", response_model=NextQuestionResponse)
async def next_question_endpoint(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    ai_provider: AIProvider = Depends(get_ai_provider),
) -> NextQuestionResponse:
    try:
        quiz_session = await get_session_or_404(session, session_id)
        question = await get_or_generate_next_question(
            session, quiz_session=quiz_session, ai_provider=ai_provider
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (QuestionGenerationError, StructuredOutputError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return NextQuestionResponse(
        completed=question is None,
        question=QuestionPayload.model_validate(question) if question else None,
    )


@router.post(
    "/v1/quiz-sessions/{session_id}/answers/{question_id}",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_answer_endpoint(
    session_id: UUID,
    question_id: UUID,
    payload: AnswerSubmissionRequest,
    session: AsyncSession = Depends(get_db_session),
    ai_provider: AIProvider = Depends(get_ai_provider),
) -> AnswerResponse:
    try:
        quiz_session = await get_session_or_404(session, session_id)
        answer = await submit_answer(
            session,
            quiz_session=quiz_session,
            question_id=question_id,
            answer_payload=payload.answer,
            ai_provider=ai_provider,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StructuredOutputError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AnswerResponse(
        question_id=answer.question_id,
        is_correct=answer.is_correct,
        score=answer.score,
        feedback=answer.feedback,
        explanation=answer.explanation,
        evaluation_mode=answer.evaluation_mode,
        next_difficulty=quiz_session.current_difficulty,
        session_completed=quiz_session.status.value == "completed",
    )


@router.get("/v1/quiz-sessions/{session_id}", response_model=QuizSessionResponse)
async def get_quiz_session_endpoint(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> QuizSessionResponse:
    try:
        quiz_session = await get_session_or_404(session, session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return QuizSessionResponse.model_validate(quiz_session)


async def _parse_source_payload(request: Request) -> SourcePayload:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="JSON body must include non-empty 'text'.")
        title = (body.get("title") or "Untitled text source").strip()
        return SourcePayload(title=title, input_type=SourceInputType.text, raw_text=text)

    form = await request.form()
    text = str(form.get("text") or "").strip()
    upload = form.get("file")
    title = str(form.get("title") or "").strip()
    if text and upload:
        raise HTTPException(status_code=422, detail="Provide either text or a PDF file, not both.")
    if text:
        return SourcePayload(
            title=title or "Untitled text source",
            input_type=SourceInputType.text,
            raw_text=text,
        )
    if isinstance(upload, (UploadFile, StarletteUploadFile)):
        if not (
            (upload.filename or "").lower().endswith(".pdf")
            or upload.content_type == "application/pdf"
        ):
            raise HTTPException(status_code=422, detail="Only PDF uploads are supported.")
        file_bytes = await upload.read()
        return SourcePayload(
            title=title or upload.filename or "Untitled PDF source",
            input_type=SourceInputType.pdf,
            pdf_bytes=file_bytes,
            original_filename=upload.filename,
        )
    raise HTTPException(status_code=422, detail="Provide text or a PDF file.")
