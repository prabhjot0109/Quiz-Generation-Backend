"""add question fingerprint"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0002"
down_revision = "20260314_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("question_fingerprint", sa.String(length=64), nullable=True),
    )
    op.execute(
        """
        UPDATE questions
        SET question_fingerprint = substr(CAST(id AS VARCHAR), 1, 64)
        WHERE question_fingerprint IS NULL
        """
    )
    op.alter_column("questions", "question_fingerprint", nullable=False)
    op.create_index(
        "ix_questions_session_id_question_fingerprint",
        "questions",
        ["session_id", "question_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_questions_session_id_question_fingerprint", table_name="questions")
    op.drop_column("questions", "question_fingerprint")
