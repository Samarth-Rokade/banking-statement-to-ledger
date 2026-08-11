"""add ledger/group/confidence/resolution columns to parsed_transactions

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    resolution_source_enum = sa.Enum(
        "RULE",
        "EXACT_MATCH",
        "ALIAS_MATCH",
        "SIMILARITY_MATCH",
        "AI_PREDICTION",
        "MANUAL",
        "AI_FAILED",
        name="resolutionsource",
    )
    resolution_source_enum.create(op.get_bind(), checkfirst=True)

    # SQLite can't ALTER-add a column with a foreign key constraint directly; batch
    # mode uses its copy-and-move strategy there and is a plain passthrough on
    # Postgres, so this works unchanged on both.
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ledger_id",
                GUID(),
                sa.ForeignKey("ledgers.id", name="fk_parsed_transactions_ledger_id"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "group_id",
                GUID(),
                sa.ForeignKey("ledger_groups.id", name="fk_parsed_transactions_group_id"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("confidence", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("resolution_source", resolution_source_enum, nullable=True)
        )
        batch_op.add_column(
            sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_index("ix_parsed_transactions_ledger_id", "parsed_transactions", ["ledger_id"])
    op.create_index(
        "ix_parsed_transactions_requires_review", "parsed_transactions", ["requires_review"]
    )


def downgrade() -> None:
    op.drop_index("ix_parsed_transactions_requires_review", table_name="parsed_transactions")
    op.drop_index("ix_parsed_transactions_ledger_id", table_name="parsed_transactions")
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.drop_column("requires_review")
        batch_op.drop_column("resolution_source")
        batch_op.drop_column("confidence")
        batch_op.drop_column("group_id")
        batch_op.drop_column("ledger_id")
    sa.Enum(name="resolutionsource").drop(op.get_bind(), checkfirst=True)
