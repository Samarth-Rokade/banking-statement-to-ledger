"""create parsed_transactions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parsed_transactions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "processing_job_id", GUID(), sa.ForeignKey("processing_jobs.id"), nullable=False
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("original_narration", sa.String(), nullable=False),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("debit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_parsed_transactions_processing_job_id", "parsed_transactions", ["processing_job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_parsed_transactions_processing_job_id", table_name="parsed_transactions")
    op.drop_table("parsed_transactions")
