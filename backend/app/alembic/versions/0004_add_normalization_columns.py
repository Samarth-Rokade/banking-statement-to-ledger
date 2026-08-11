"""add normalized_narration and transaction_type_tag to parsed_transactions

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parsed_transactions", sa.Column("normalized_narration", sa.String(), nullable=True))
    op.add_column("parsed_transactions", sa.Column("transaction_type_tag", sa.String(), nullable=True))
    op.create_index(
        "ix_parsed_transactions_transaction_type_tag",
        "parsed_transactions",
        ["transaction_type_tag"],
    )


def downgrade() -> None:
    op.drop_index("ix_parsed_transactions_transaction_type_tag", table_name="parsed_transactions")
    op.drop_column("parsed_transactions", "transaction_type_tag")
    op.drop_column("parsed_transactions", "normalized_narration")
