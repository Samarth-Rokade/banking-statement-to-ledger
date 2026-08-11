"""create ai_predictions audit table

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.utils.types import GUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")

    op.create_table(
        "ai_predictions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "parsed_transaction_id", GUID(), sa.ForeignKey("parsed_transactions.id"), nullable=False
        ),
        sa.Column("prompt_name", sa.String(), nullable=False),
        sa.Column("model_used", sa.String(), nullable=False),
        sa.Column("raw_request", json_type, nullable=False),
        sa.Column("raw_response", json_type, nullable=True),
        sa.Column("predicted_confidence", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ai_predictions_parsed_transaction_id", "ai_predictions", ["parsed_transaction_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_predictions_parsed_transaction_id", table_name="ai_predictions")
    op.drop_table("ai_predictions")
