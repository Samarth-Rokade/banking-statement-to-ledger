"""create uploaded_files and processing_jobs tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.utils.types import GUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Native ENUM on Postgres, CHECK-constrained VARCHAR on other dialects (e.g. SQLite) -
# sa.Enum handles that adaptation automatically, unlike dialects.postgresql.ENUM.
file_type_enum = sa.Enum("PDF", "CSV", "XLSX", name="filetype")
job_status_enum = sa.Enum(
    "QUEUED",
    "PARSING",
    "NORMALIZING",
    "MATCHING",
    "AI_PREDICTING",
    "VALIDATING",
    "REVIEW_REQUIRED",
    "READY",
    "EXPORTED",
    "FAILED",
    name="jobstatus",
)

# Native JSONB on Postgres, generic JSON elsewhere - mirrors the model's column type.
status_history_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    file_type_enum.create(bind, checkfirst=True)
    job_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "uploaded_files",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("file_type", file_type_enum, nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_uploaded_files_checksum_sha256", "uploaded_files", ["checksum_sha256"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("uploaded_file_id", GUID(), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("status_history", status_history_type, nullable=False),
        sa.Column("total_transactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_predicted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual_review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("export_ready_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("uploaded_files")
    job_status_enum.drop(op.get_bind(), checkfirst=True)
    file_type_enum.drop(op.get_bind(), checkfirst=True)
