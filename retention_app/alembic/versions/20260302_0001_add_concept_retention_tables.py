"""add concept retention tables

Revision ID: 20260302_0001
Revises:
Create Date: 2026-03-02 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("aliases_json", sa.Text(), nullable=True),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "canonical_name", name="uq_concepts_user_canonical"),
    )
    op.create_index("ix_concepts_user_id", "concepts", ["user_id"], unique=False)

    op.create_table(
        "concept_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("concept_id", sa.Integer(), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("support_strength", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_concept_evidence_concept_id", "concept_evidence", ["concept_id"], unique=False)
    op.create_index("ix_concept_evidence_content_id", "concept_evidence", ["content_id"], unique=False)

    op.create_table(
        "concept_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default=sa.text("2.5")),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bloom_stage", sa.String(length=32), nullable=False, server_default="Knowledge"),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "concept_id", name="uq_concept_schedules_user_concept"),
    )
    op.create_index("ix_concept_schedules_user_id", "concept_schedules", ["user_id"], unique=False)
    op.create_index("ix_concept_schedules_concept_id", "concept_schedules", ["concept_id"], unique=False)
    op.create_index("ix_concept_schedules_due_at", "concept_schedules", ["due_at"], unique=False)
    op.create_index("ix_concept_schedules_user_due", "concept_schedules", ["user_id", "due_at"], unique=False)

    op.create_table(
        "question_probes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("concept_id", sa.Integer(), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("bloom_level", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("generation_model", sa.String(length=100), nullable=True),
        sa.Column("generation_prompt_version", sa.String(length=50), nullable=True),
        sa.Column("generation_metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_question_probes_concept_id", "question_probes", ["concept_id"], unique=False)

    op.create_table(
        "review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("question_probe_id", sa.Integer(), sa.ForeignKey("question_probes.id"), nullable=True),
        sa.Column("self_comfort", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_review_events_user_id", "review_events", ["user_id"], unique=False)
    op.create_index("ix_review_events_concept_id", "review_events", ["concept_id"], unique=False)
    op.create_index(
        "ix_review_events_concept_created",
        "review_events",
        ["concept_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_events_concept_created", table_name="review_events")
    op.drop_index("ix_review_events_concept_id", table_name="review_events")
    op.drop_index("ix_review_events_user_id", table_name="review_events")
    op.drop_table("review_events")

    op.drop_index("ix_question_probes_concept_id", table_name="question_probes")
    op.drop_table("question_probes")

    op.drop_index("ix_concept_schedules_user_due", table_name="concept_schedules")
    op.drop_index("ix_concept_schedules_due_at", table_name="concept_schedules")
    op.drop_index("ix_concept_schedules_concept_id", table_name="concept_schedules")
    op.drop_index("ix_concept_schedules_user_id", table_name="concept_schedules")
    op.drop_table("concept_schedules")

    op.drop_index("ix_concept_evidence_content_id", table_name="concept_evidence")
    op.drop_index("ix_concept_evidence_concept_id", table_name="concept_evidence")
    op.drop_table("concept_evidence")

    op.drop_index("ix_concepts_user_id", table_name="concepts")
    op.drop_table("concepts")
