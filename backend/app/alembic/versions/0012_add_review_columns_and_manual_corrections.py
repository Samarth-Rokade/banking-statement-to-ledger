"""add reviewed_by_user_id/reviewed_at to parsed_transactions, create manual_corrections

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "reviewed_by_user_id",
                GUID(),
                sa.ForeignKey("users.id", name="fk_parsed_transactions_reviewed_by_user"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "manual_corrections",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "parsed_transaction_id",
            GUID(),
            sa.ForeignKey("parsed_transactions.id"),
            nullable=False,
        ),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "field_changed",
            sa.Enum("LEDGER", "GROUP", "VOUCHER", name="correctionfield"),
            nullable=False,
        ),
        sa.Column("old_value", sa.String(), nullable=True),
        sa.Column("new_value", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_manual_corrections_parsed_transaction_id", "manual_corrections", ["parsed_transaction_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_manual_corrections_parsed_transaction_id", table_name="manual_corrections")
    op.drop_table("manual_corrections")
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by_user_id")
