"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("auth_provider", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False),
        sa.Column("is_public_rank", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # Questions table
    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("supporting_code", sa.Text(), nullable=True),
        sa.Column("supporting_logs", sa.Text(), nullable=True),
        sa.Column("supporting_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("category", sa.Enum("software_engineering", "data_science", "data_engineering", "cyber_security", name="question_category"), nullable=False),
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("difficulty", sa.Enum("low", "medium", "high", name="question_difficulty"), nullable=False),
        sa.Column("is_vetted", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("generation_source", sa.Enum("human", "ai_pipeline", name="generation_source"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Assessment sessions
    op.create_table(
        "assessment_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mode", sa.Enum("trial", "practice", "exam", name="session_mode"), nullable=False),
        sa.Column("difficulty", sa.Enum("low", "medium", "high", name="session_difficulty"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("pending", "in_progress", "completed", "abandoned", "flagged", name="session_status"), nullable=False),
        sa.Column("is_flagged_for_review", sa.Boolean(), nullable=False),
        sa.Column("flag_reason", sa.String(1000), nullable=True),
        sa.Column("ai_assistant_disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessment_sessions_user_id", "assessment_sessions", ["user_id"])

    # Session questions
    op.create_table(
        "session_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("code_response", sa.Text(), nullable=True),
        sa.Column("ai_interactions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score_engineering_skill", sa.Float(), nullable=True),
        sa.Column("score_ai_collaboration", sa.Float(), nullable=True),
        sa.Column("score_ai_trust_calibration", sa.Float(), nullable=True),
        sa.Column("score_engineering_judgement", sa.Float(), nullable=True),
        sa.Column("scoring_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_questions_session_id", "session_questions", ["session_id"])

    # Session events
    op.create_table(
        "session_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Enum("leave_page", "return_to_page", "inactivity_warning", "tab_blur", "copy_paste", name="event_type"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_events_session_id", "session_events", ["session_id"])

    # Session scores
    op.create_table(
        "session_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("pending", "completed", "failed", name="score_status"), nullable=False),
        sa.Column("engineering_skill", sa.Float(), nullable=True),
        sa.Column("ai_collaboration", sa.Float(), nullable=True),
        sa.Column("ai_trust_calibration", sa.Float(), nullable=True),
        sa.Column("engineering_judgement", sa.Float(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("percentile_rank", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_session_scores_session_id", "session_scores", ["session_id"])

    # Certificates
    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_url", sa.String(2048), nullable=False),
        sa.Column("share_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("linkedin_url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        sa.UniqueConstraint("share_token"),
    )
    op.create_index("ix_certificates_user_id", "certificates", ["user_id"])
    op.create_index("ix_certificates_session_id", "certificates", ["session_id"])
    op.create_index("ix_certificates_share_token", "certificates", ["share_token"])

    # Saved topics
    op.create_table(
        "saved_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_name", sa.String(500), nullable=False),
        sa.Column("study_url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_topics_user_id", "saved_topics", ["user_id"])

    # Pipeline runs
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("running", "completed", "failed", name="pipeline_status"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("difficulty", sa.String(50), nullable=False),
        sa.Column("generated_count", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("held_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
    op.drop_table("saved_topics")
    op.drop_table("certificates")
    op.drop_table("session_scores")
    op.drop_table("session_events")
    op.drop_table("session_questions")
    op.drop_table("assessment_sessions")
    op.drop_table("questions")
    op.drop_table("users")

    # Drop enums
    for enum_name in [
        "pipeline_status", "score_status", "event_type",
        "session_status", "session_difficulty", "session_mode",
        "generation_source", "question_difficulty", "question_category",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
