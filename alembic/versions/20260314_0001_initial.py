"""initial schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260314_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    source_input_type = postgresql.ENUM(
        "text", "pdf", name="sourceinputtype", create_type=False
    )
    source_status = postgresql.ENUM(
        "pending", "processing", "ready", "failed", name="sourcestatus", create_type=False
    )
    difficulty_level = postgresql.ENUM(
        "easy", "medium", "hard", name="difficultylevel", create_type=False
    )
    question_type = postgresql.ENUM(
        "mcq", "true_false", "fill_blank", "short_answer", name="questiontype", create_type=False
    )
    session_status = postgresql.ENUM(
        "active", "completed", name="sessionstatus", create_type=False
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        source_input_type.create(bind, checkfirst=True)
        source_status.create(bind, checkfirst=True)
        difficulty_level.create(bind, checkfirst=True)
        question_type.create(bind, checkfirst=True)
        session_status.create(bind, checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("input_type", source_input_type, nullable=False),
        sa.Column("status", source_status, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )
    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("search_document", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_source_chunks_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_chunks")),
    )
    op.create_index(
        "ix_source_chunks_source_id_chunk_index",
        "source_chunks",
        ["source_id", "chunk_index"],
        unique=False,
    )
    op.create_table(
        "quiz_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("status", session_status, nullable=False),
        sa.Column("current_difficulty", difficulty_level, nullable=False),
        sa.Column("target_question_count", sa.Integer(), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("generated_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), nullable=False),
        sa.Column("last_score", sa.Float(), nullable=True),
        sa.Column("question_types", sa.JSON(), nullable=False),
        sa.Column("recent_outcomes", sa.JSON(), nullable=False),
        sa.Column("focus_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_quiz_sessions_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_sessions")),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_type", question_type, nullable=False),
        sa.Column("difficulty", difficulty_level, nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("chunk_refs", sa.JSON(), nullable=False),
        sa.Column("answer_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["quiz_sessions.id"], name=op.f("fk_questions_session_id_quiz_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_questions_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_answer", sa.JSON(), nullable=False),
        sa.Column("normalized_answer", sa.String(length=512), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("evaluation_mode", sa.String(length=32), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name=op.f("fk_answers_question_id_questions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["quiz_sessions.id"], name=op.f("fk_answers_session_id_quiz_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_answers")),
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_source_chunks_search_vector
            ON source_chunks
            USING gin (to_tsvector('english', search_document))
            """
        )
    else:
        op.create_index(
            "ix_source_chunks_search_document",
            "source_chunks",
            ["search_document"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_source_chunks_search_vector")
    else:
        op.drop_index("ix_source_chunks_search_document", table_name="source_chunks")

    op.drop_table("answers")
    op.drop_table("questions")
    op.drop_table("quiz_sessions")
    op.drop_index("ix_source_chunks_source_id_chunk_index", table_name="source_chunks")
    op.drop_table("source_chunks")
    op.drop_table("sources")

    if bind.dialect.name == "postgresql":
        sa.Enum(name="sessionstatus").drop(bind, checkfirst=True)
        sa.Enum(name="questiontype").drop(bind, checkfirst=True)
        sa.Enum(name="difficultylevel").drop(bind, checkfirst=True)
        sa.Enum(name="sourcestatus").drop(bind, checkfirst=True)
        sa.Enum(name="sourceinputtype").drop(bind, checkfirst=True)
