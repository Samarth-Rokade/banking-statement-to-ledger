"""add is_duplicate/duplicate_of_transaction_id/validation_errors to parsed_transactions

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.utils.types import GUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")

    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.add_column(
            sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column(
                "duplicate_of_transaction_id",
                GUID(),
                sa.ForeignKey(
                    "parsed_transactions.id", name="fk_parsed_transactions_duplicate_of"
                ),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("validation_errors", json_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.drop_column("validation_errors")
        batch_op.drop_column("duplicate_of_transaction_id")
        batch_op.drop_column("is_duplicate")
