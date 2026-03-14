# Peblo Quiz Backend

Local-first FastAPI backend for the Peblo AI Backend Engineer Challenge. The service ingests text or PDF content, chunks and indexes it in PostgreSQL, generates adaptive quiz questions, and scores answers with deterministic logic plus Gemini-backed short-answer evaluation.

## Stack

- FastAPI
- SQLAlchemy 2 + asyncpg
- Alembic
- PostgreSQL
- Gemini Flash via Google Generative Language REST API

## Run Locally

1. Copy `.env.example` to `.env`.
2. Start PostgreSQL:

```bash
docker compose up -d db
```

3. Install dependencies:

```bash
pip install -e .[dev]
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

## Environment

- Evaluator/local Postgres:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/peblo_db
```

- Hosted Postgres or Supabase Postgres:

```env
DATABASE_URL=postgresql+asyncpg://postgres:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres
```

The application only depends on `DATABASE_URL`. No Supabase SDK is used.

## API

- `POST /v1/sources`
  - JSON: `{ "title": "...", "text": "..." }`
  - Multipart: `title`, `file=<pdf>`
- `GET /v1/sources/{source_id}`
- `POST /v1/quiz-sessions`
- `GET /v1/quiz-sessions/{session_id}/next-question`
- `POST /v1/quiz-sessions/{session_id}/answers/{question_id}`
- `GET /v1/quiz-sessions/{session_id}`
- `GET /health`

## Notes

- PDF ingestion supports text-extractable PDFs only.
- Objective questions are scored deterministically.
- Short-answer evaluation uses Gemini when `GEMINI_API_KEY` is set; otherwise a local mock evaluator is used so the app remains runnable in development and tests.
- Adaptive difficulty is rule-based:
  - two recent correct answers increase difficulty
  - two recent incorrect answers decrease difficulty

## Tests

```bash
pytest
```
