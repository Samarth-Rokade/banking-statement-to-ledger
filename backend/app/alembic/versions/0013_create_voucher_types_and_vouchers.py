"""create voucher_types (seeded), vouchers, and parsed_transactions.voucher_type_id

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-12
"""

import uuid

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_VOUCHER_TYPES = ["Receipt", "Payment", "Contra", "Journal"]


def upgrade() -> None:
    op.create_table(
        "voucher_types",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    voucher_types_table = sa.table(
        "voucher_types", sa.column("id", GUID()), sa.column("name", sa.String())
    )
    op.bulk_insert(
        voucher_types_table, [{"id": str(uuid.uuid4()), "name": name} for name in _VOUCHER_TYPES]
    )

    op.create_table(
        "vouchers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "parsed_transaction_id",
            GUID(),
            sa.ForeignKey("parsed_transactions.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("voucher_type_id", GUID(), sa.ForeignKey("voucher_types.id"), nullable=False),
        sa.Column("voucher_number", sa.String(), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "voucher_type_id",
                GUID(),
                sa.ForeignKey("voucher_types.id", name="fk_parsed_transactions_voucher_type"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.drop_column("voucher_type_id")

    op.drop_table("vouchers")
    op.drop_table("voucher_types")
