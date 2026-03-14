<div align="center">

# 🧠 Peblo Quiz Engine

**AI-powered content ingestion and adaptive quiz generation backend**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Gemini AI](https://img.shields.io/badge/Gemini_AI-8E75B2?logo=googlegemini&logoColor=white)](https://ai.google.dev)

---

*Ingest PDFs → Extract & chunk content → Generate adaptive quizzes → Adjust difficulty in real time*

</div>

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Adaptive Difficulty](#adaptive-difficulty)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Sample Outputs](#sample-outputs)
- [Challenge Compliance](#challenge-compliance)

---

## Overview

Peblo Quiz Engine is a backend system that transforms raw educational content (PDFs or plain text) into structured, adaptive quiz experiences. It implements the full pipeline from content ingestion through quiz generation to real-time difficulty adjustment based on student performance.

### Key Capabilities

| Capability | Description |
|---|---|
| **Content Ingestion** | Upload PDFs or raw text; the system extracts, cleans, and chunks content automatically |
| **Structured Storage** | PostgreSQL-backed storage for sources, chunks, quiz sessions, questions, and answers |
| **AI Quiz Generation** | Generates MCQ, True/False, Fill-in-the-blank, and Short Answer questions via Google Gemini |
| **Source Traceability** | Every generated question links back to its source chunk(s) via `chunk_refs` |
| **Adaptive Difficulty** | Rule-based engine adjusts difficulty (easy → medium → hard) based on recent answer patterns |
| **Duplicate Detection** | SHA-256 fingerprinting prevents duplicate questions within a session |
| **Graceful Fallback** | Runs without an API key using a local mock AI provider for development and testing |

---

## Architecture

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  PDF / Text   │────▶│   Ingestion   │────▶│   PostgreSQL  │
│   Upload      │     │   Pipeline    │     │   Storage     │
└───────────────┘     └───────────────┘     └───────┬───────┘
                                                    │
                      ┌───────────────┐             │
                      │   Gemini AI   │◀────────────┤
                      │   Provider    │             │
                      └───────┬───────┘             │
                              │                     │
                      ┌───────▼───────┐     ┌───────▼───────┐
                      │    Quiz       │────▶│   Adaptive    │
                      │  Generation   │     │   Scoring     │
                      └───────────────┘     └───────────────┘
```

### Data Flow

1. **Ingest** — Client uploads a PDF or submits text via `POST /v1/sources`. The system creates a source record (status: `processing`) and begins async extraction.
2. **Extract & Chunk** — Text is extracted from PDFs using PyPDF, normalized, then split into overlapping chunks with configurable size and overlap.
3. **Metadata Enrichment** — Grade level, subject, and topic are automatically inferred from the source title and content.
4. **Quiz Session** — Client creates a session tied to a source, specifying desired question types and count.
5. **Question Generation** — On each `next-question` call, the engine selects relevant chunks *(with optional full-text-search focus)*, sends them to Gemini, validates the structured JSON response, and stores the question.
6. **Answer & Adapt** — Student submits an answer. Objective types (MCQ, True/False, Fill-in-the-blank) are scored deterministically. Short answers are evaluated by Gemini. Difficulty adjusts based on the last two outcomes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | FastAPI with async/await throughout |
| **Database** | PostgreSQL 16 via SQLAlchemy 2 + asyncpg |
| **Migrations** | Alembic |
| **AI** | Google Gemini (structured JSON output mode) |
| **PDF Parsing** | PyPDF |
| **HTTP Client** | httpx (async) |
| **Config** | pydantic-settings with `.env` file support |
| **Testing** | pytest + pytest-asyncio with in-memory SQLite |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker (for local PostgreSQL) **or** a hosted PostgreSQL URL
- A Google Gemini API key

### 1. Clone & Configure

```bash
git clone https://github.com/prabhjot0109/Quiz-Generation-Backend.git
cd Quiz-Generation-Backend
cp .env.example .env
```

Edit `.env` and set your `DATABASE_URL` and optionally `GEMINI_API_KEY`.

### 2. Start PostgreSQL

```bash
docker compose up -d db
```

> **Using hosted PostgreSQL?** Skip this step and set `DATABASE_URL` in `.env` to your connection string.

### 3. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 4. Run Migrations

```bash
alembic upgrade head
```

### 5. Start the Server

```bash
uvicorn app.main:app --reload
```

The API is now live at [`http://127.0.0.1:8000`](http://127.0.0.1:8000). Interactive docs at [`/docs`](http://127.0.0.1:8000/docs).

### 6. Ingest a PDF

```bash
curl -X POST http://127.0.0.1:8000/v1/sources \
  -F "title=Grade 1 Math" \
  -F "file=@data/pdfs/peblo_pdf_grade1_math_numbers.pdf;type=application/pdf"
```

Poll until ready:

```bash
curl http://127.0.0.1:8000/v1/sources/{source_id}
# Wait until "status": "ready"
```

### 7. Generate a Quiz

```bash
# Create a session
curl -X POST http://127.0.0.1:8000/v1/quiz-sessions \
  -H "Content-Type: application/json" \
  -d '{"source_id": "<source_id>", "question_count": 5, "question_types": ["mcq", "true_false", "fill_blank"]}'

# Fetch questions one by one
curl http://127.0.0.1:8000/v1/quiz-sessions/{session_id}/next-question

# Submit an answer
curl -X POST http://127.0.0.1:8000/v1/quiz-sessions/{session_id}/answers/{question_id} \
  -H "Content-Type: application/json" \
  -d '{"answer": {"choice_id": "b"}}'
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | `postgresql+asyncpg://user:password@localhost:5432/peblo_db` | PostgreSQL connection string |
| `GEMINI_API_KEY` | No | `null` | Google Gemini API key. When unset, the mock AI provider is used |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Gemini model identifier |
| `AI_REQUEST_TIMEOUT_SECONDS` | No | `20` | Timeout for each Gemini API call |
| `AI_MAX_RETRIES` | No | `2` | Retry count for invalid structured output from Gemini |
| `DEFAULT_QUESTION_COUNT` | No | `5` | Default number of questions per quiz session |
| `CHUNK_SIZE` | No | `900` | Character limit per text chunk |
| `CHUNK_OVERLAP` | No | `120` | Overlap between consecutive chunks |

> **Note:** The application only depends on `DATABASE_URL`. No Supabase SDK or other third-party database abstraction is used.

---

## API Reference

### Health Check

```
GET /health
```

Returns `{"status": "ok"}` when the server is running.

---

### Sources

#### Create Source

```
POST /v1/sources
```

Accepts **JSON** or **multipart form data**.

<details>
<summary><strong>JSON body</strong> — for plain text</summary>

```json
{
  "title": "Learning Science",
  "text": "Formative assessment uses regular feedback..."
}
```
</details>

<details>
<summary><strong>Multipart</strong> — for PDF upload</summary>

```bash
curl -X POST http://127.0.0.1:8000/v1/sources \
  -F "title=Grade 1 Math" \
  -F "file=@document.pdf;type=application/pdf"
```
</details>

**Response** `202 Accepted`

```json
{
  "id": "117f7759-dd48-4472-98b8-b68b3fe0f2b5",
  "title": "Grade 1 Math",
  "input_type": "pdf",
  "status": "processing",
  "original_filename": "document.pdf",
  "summary": null,
  "error_message": null,
  "created_at": "2026-03-14T15:04:52Z",
  "updated_at": "2026-03-14T15:04:52Z"
}
```

> Processing happens asynchronously. Poll the detail endpoint until `status` is `ready`.

#### Get Source Detail

```
GET /v1/sources/{source_id}
```

Returns the source with its chunks and metadata once processing is complete.

**Response** `200 OK`

```json
{
  "id": "117f7759-dd48-4472-98b8-b68b3fe0f2b5",
  "title": "Grade 1 Math",
  "input_type": "pdf",
  "status": "ready",
  "chunk_count": 1,
  "chunks": [
    {
      "id": "61e45d2a-9fe8-4cc3-a317-592ad0003ca5",
      "chunk_index": 0,
      "content": "Peblo Sample Content – Grade 1 Mathematics...",
      "metadata": {
        "start_char": 0,
        "end_char": 751,
        "grade": 1,
        "subject": "Math",
        "topic": "Numbers, Counting and Shapes"
      }
    }
  ]
}
```

---

### Quiz Sessions

#### Create Session

```
POST /v1/quiz-sessions
```

```json
{
  "source_id": "117f7759-dd48-4472-98b8-b68b3fe0f2b5",
  "question_count": 5,
  "question_types": ["mcq", "true_false", "fill_blank", "short_answer"],
  "focus_text": "shapes"
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `source_id` | UUID | *required* | Source to generate questions from |
| `question_count` | int (1-20) | `5` | Number of questions in this session |
| `question_types` | string[] | all four types | Cycle through these types in order |
| `focus_text` | string | `null` | Optional keyword to focus chunk retrieval |

**Response** `201 Created`

```json
{
  "id": "b14e05de-462c-4b16-8ac3-7ad8df8193c6",
  "source_id": "117f7759-dd48-4472-98b8-b68b3fe0f2b5",
  "status": "active",
  "current_difficulty": "medium",
  "target_question_count": 5,
  "answered_count": 0,
  "generated_count": 0,
  "correct_count": 0,
  "incorrect_count": 0,
  "last_score": null,
  "question_types": ["mcq", "true_false", "fill_blank", "short_answer"],
  "recent_outcomes": []
}
```

#### Get Next Question

```
GET /v1/quiz-sessions/{session_id}/next-question
```

Returns the next unanswered question. If all questions have been answered and the target count is reached, returns `{"completed": true}`.

**Response** `200 OK`

```json
{
  "completed": false,
  "question": {
    "id": "de06d19e-50fa-4d87-b069-67c578b7cf22",
    "session_id": "b14e05de-462c-4b16-8ac3-7ad8df8193c6",
    "source_id": "117f7759-dd48-4472-98b8-b68b3fe0f2b5",
    "position": 1,
    "question_type": "mcq",
    "difficulty": "medium",
    "prompt": "How many sides does a triangle have?",
    "options": [
      {"id": "a", "text": "2"},
      {"id": "b", "text": "3"},
      {"id": "c", "text": "4"},
      {"id": "d", "text": "5"}
    ],
    "explanation": "A triangle has exactly three sides.",
    "chunk_refs": ["61e45d2a-9fe8-4cc3-a317-592ad0003ca5"],
    "answer_submitted": false
  }
}
```

#### Submit Answer

```
POST /v1/quiz-sessions/{session_id}/answers/{question_id}
```

Answer format depends on question type:

| Question Type | Answer Payload |
|---|---|
| MCQ | `{"answer": {"choice_id": "b"}}` |
| True/False | `{"answer": {"value": true}}` |
| Fill in the blank | `{"answer": {"value": "triangle"}}` |
| Short answer | `{"answer": {"value": "A triangle has three sides..."}}` |

**Response** `201 Created`

```json
{
  "question_id": "de06d19e-50fa-4d87-b069-67c578b7cf22",
  "is_correct": true,
  "score": 1.0,
  "feedback": "Correct answer.",
  "explanation": "A triangle has exactly three sides.",
  "evaluation_mode": "deterministic",
  "next_difficulty": "medium",
  "session_completed": false
}
```

#### Get Session State

```
GET /v1/quiz-sessions/{session_id}
```

Returns the full session state including progression counters, current difficulty, and recent outcomes.

---

## Adaptive Difficulty

The engine adjusts quiz difficulty using a **sliding-window rule** over the student's last two answers:

```
┌─────────────────────────────────────────────────────┐
│  Last 2 answers both CORRECT  →  difficulty UP      │
│  Last 2 answers both INCORRECT  →  difficulty DOWN  │
│  Mixed results  →  no change                        │
└─────────────────────────────────────────────────────┘

         easy  ──▶  medium  ──▶  hard
         easy  ◀──  medium  ◀──  hard
```

| Scenario | Current | Recent Outcomes | Next |
|---|---|---|---|
| Two correct in a row | `medium` | `[true, true]` | `hard` |
| Two incorrect in a row | `hard` | `[false, false]` | `medium` |
| Mixed | `medium` | `[true, false]` | `medium` |
| Already at ceiling | `hard` | `[true, true]` | `hard` |

The session response exposes `current_difficulty`, `recent_outcomes`, and `next_difficulty` so clients can display the progression.

---

## Project Structure

```
Quiz-Generation-Backend/
├── app/
│   ├── main.py                  # FastAPI app factory and lifespan
│   ├── core/
│   │   ├── config.py            # Pydantic settings from .env
│   │   └── database.py          # Engine & session factory (legacy)
│   ├── contracts/
│   │   ├── ai.py                # Pydantic schemas for AI input/output
│   │   ├── quiz.py              # Request/response models for quiz APIs
│   │   └── source.py            # Request/response models for source APIs
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM models (5 tables)
│   │   └── session.py           # DatabaseManager class
│   ├── http/
│   │   ├── routes.py            # All API route handlers
│   │   └── dependencies.py      # FastAPI dependency injection
│   ├── logic/
│   │   ├── ai.py                # Gemini + Mock AI providers
│   │   ├── quiz_service.py      # Session/question/answer orchestration
│   │   ├── retrieval.py         # Chunk retrieval with full-text search
│   │   ├── scoring.py           # Deterministic scoring + adaptive logic
│   │   └── source_service.py    # Source creation + async processing
│   └── services/
│       ├── chunking.py          # Text normalization + chunk splitting
│       └── pdf.py               # PDF text extraction via PyPDF
├── alembic/                     # Database migration scripts
├── data/pdfs/                   # Place Peblo evaluation PDFs here
├── samples/                     # Pre-generated sample outputs
├── scripts/                     # Automation scripts
├── tests/                       # pytest test suite
├── .env.example                 # Environment variable template
├── docker-compose.yml           # Local PostgreSQL container
├── pyproject.toml               # Project metadata and dependencies
└── alembic.ini                  # Alembic configuration
```

---

## Testing

Tests run against an in-memory SQLite database using the mock AI provider — no external dependencies required.

```bash
pip install -e ".[dev]"
pytest
```

```
tests/test_sources.py        — Source ingestion and chunking
tests/test_quiz_flow.py      — End-to-end quiz flow with adaptive difficulty
tests/test_ai_reliability.py — Gemini provider retry and structured output validation
```

All 6 tests cover the full lifecycle: ingestion → chunking → session creation → question generation → answer submission → difficulty adjustment.

---

## Sample Outputs

The `samples/` directory contains pre-generated outputs from a real run against the three Peblo evaluation PDFs:

| File | Contents |
|---|---|
| [`extracted_source.json`](samples/extracted_source.json) | Source detail with chunks and metadata after PDF ingestion |
| [`generated_quiz_question.json`](samples/generated_quiz_question.json) | Generated questions for MCQ, True/False, and Fill-in-the-blank |
| [`api_responses.json`](samples/api_responses.json) | Full API response log: health, ingestion, session, adaptive flow |
| [`database_schema.md`](samples/database_schema.md) | Schema snapshot of all 5 database tables |
| [`challenge_compliance_report.md`](samples/challenge_compliance_report.md) | Requirement-by-requirement compliance checklist |

To regenerate samples with a live server:

```powershell
# Start the server first, then:
pwsh scripts/evaluate_and_refresh_samples.ps1
```

---

## Challenge Compliance

| Requirement | Status | Implementation |
|---|---|---|
| Content ingestion from PDF | ✅ | `POST /v1/sources` with multipart PDF |
| Extract + clean + chunk content | ✅ | PyPDF extraction → text normalization → overlapping chunks |
| Structured storage | ✅ | PostgreSQL with 5 normalized tables |
| Quiz generation via LLM | ✅ | Gemini with structured JSON output + mock fallback |
| MCQ questions | ✅ | Supported via `question_types` parameter |
| True/False questions | ✅ | Supported via `question_types` parameter |
| Fill-in-the-blank questions | ✅ | Supported via `question_types` parameter |
| Quiz retrieval API | ✅ | `GET /v1/quiz-sessions/{id}/next-question` |
| Student answer submission | ✅ | `POST /v1/quiz-sessions/{id}/answers/{qid}` |
| Adaptive difficulty | ✅ | Sliding-window rule over last 2 outcomes |
| Source traceability | ✅ | Every question includes `chunk_refs` |
| `.env.example` provided | ✅ | All variables documented with defaults |
| Sample outputs | ✅ | `samples/` directory with 5 artifacts |

### Optional Features

| Feature | Status |
|---|---|
| Duplicate question detection | ✅ SHA-256 fingerprinting per session |
| Question validation | ✅ Pydantic schema enforcement on AI output |
| Short answer evaluation | ✅ AI-powered with keyword fallback |
| Graceful AI fallback | ✅ Mock provider when no API key is set |
