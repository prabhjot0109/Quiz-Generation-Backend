# Database Schema Snapshot

This project stores ingestion, quiz generation, and student answer data in PostgreSQL.

## Core tables

### sources

- id (uuid, primary key)
- title
- input_type (text | pdf)
- status (pending | processing | ready | failed)
- original_filename
- extracted_text
- summary
- error_message
- created_at
- updated_at

### source_chunks

- id (uuid, primary key)
- source_id (foreign key -> sources.id)
- chunk_index
- content
- metadata_json
- search_document
- created_at
- updated_at

### quiz_sessions

- id (uuid, primary key)
- source_id (foreign key -> sources.id)
- status (active | completed)
- current_difficulty (easy | medium | hard)
- target_question_count
- answered_count
- generated_count
- correct_count
- incorrect_count
- last_score
- question_types (json)
- recent_outcomes (json)
- focus_text
- created_at
- updated_at

### questions

- id (uuid, primary key)
- session_id (foreign key -> quiz_sessions.id)
- source_id (foreign key -> sources.id)
- position
- question_type (mcq | true_false | fill_blank | short_answer)
- difficulty (easy | medium | hard)
- prompt
- options (json)
- correct_answer (json)
- explanation
- chunk_refs (json)
- question_fingerprint
- answer_submitted
- created_at
- updated_at

### answers

- id (uuid, primary key)
- session_id (foreign key -> quiz_sessions.id)
- question_id (foreign key -> questions.id)
- submitted_answer (json)
- normalized_answer
- is_correct
- score
- evaluation_mode
- feedback
- explanation
- created_at
- updated_at

## Optional SQL dump command

Run this against your PostgreSQL database to generate a schema-only dump:

```bash
pg_dump "$DATABASE_URL" --schema-only --no-owner --file samples/schema.sql
```
