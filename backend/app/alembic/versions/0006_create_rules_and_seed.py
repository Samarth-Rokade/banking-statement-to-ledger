"""create rules table, seed deterministic tag-based rules

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-04
"""

import uuid

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    rule_type_enum = sa.Enum("TAG", "KEYWORD", "REGEX", "CONFIG", name="ruletype")
    rule_type_enum.create(op.get_bind(), checkfirst=True)
    direction_enum = sa.Enum("DEBIT", "CREDIT", name="ruledirection")
    direction_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "rules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("rule_type", rule_type_enum, nullable=False),
        sa.Column("pattern", sa.String(), nullable=False),
        sa.Column("direction", direction_enum, nullable=True),
        sa.Column("ledger_name", sa.String(), nullable=True),
        sa.Column("group_name", sa.String(), nullable=True),
        sa.Column("voucher_type", sa.String(), nullable=True),
        sa.Column("config_value", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )

    rules_table = sa.table(
        "rules",
        sa.column("id", GUID()),
        sa.column("rule_type", rule_type_enum),
        sa.column("pattern", sa.String()),
        sa.column("direction", direction_enum),
        sa.column("ledger_name", sa.String()),
        sa.column("group_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("priority", sa.Integer()),
    )
    op.bulk_insert(
        rules_table,
        [
            {
                "id": str(uuid.uuid4()),
                "rule_type": "TAG",
                "pattern": "CASH_DEPOSIT",
                "direction": None,
                "ledger_name": "Cash",
                "group_name": "Cash-in-Hand",
                "is_active": True,
                "priority": 100,
            },
            {
                "id": str(uuid.uuid4()),
                "rule_type": "TAG",
                "pattern": "ATM",
                "direction": None,
                "ledger_name": "Cash",
                "group_name": "Cash-in-Hand",
                "is_active": True,
                "priority": 100,
            },
            {
                "id": str(uuid.uuid4()),
                "rule_type": "TAG",
                "pattern": "BANK_CHARGES",
                "direction": None,
                "ledger_name": "Bank Charges",
                "group_name": "Indirect Expenses",
                "is_active": True,
                "priority": 100,
            },
            {
                "id": str(uuid.uuid4()),
                "rule_type": "TAG",
                "pattern": "INTEREST",
                "direction": "CREDIT",
                "ledger_name": "Interest Income",
                "group_name": "Indirect Incomes",
                "is_active": True,
                "priority": 100,
            },
            {
                "id": str(uuid.uuid4()),
                "rule_type": "TAG",
                "pattern": "INTEREST",
                "direction": "DEBIT",
                "ledger_name": "Interest Expense",
                "group_name": "Indirect Expenses",
                "is_active": True,
                "priority": 100,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("rules")
    sa.Enum(name="ruledirection").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ruletype").drop(op.get_bind(), checkfirst=True)
