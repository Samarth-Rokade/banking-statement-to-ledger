"""create ledger_groups and ledgers tables, seed Tally's 28 standard groups + Cash

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-04
"""

import uuid

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# name -> parent name (None = top-level). Matches Tally's fixed 28 default groups
# exactly (verified against a real "List of Default Groups and Ledgers" export).
_GROUP_TREE: dict[str, str | None] = {
    "Current Assets": None,
    "Bank Accounts": "Current Assets",
    "Cash-in-Hand": "Current Assets",
    "Deposits (Asset)": "Current Assets",
    "Loans & Advances (Asset)": "Current Assets",
    "Stock-in-Hand": "Current Assets",
    "Sundry Debtors": "Current Assets",
    "Fixed Assets": None,
    "Investments": None,
    "Misc. Expenses (ASSET)": None,
    "Branch / Divisions": None,
    "Capital Account": None,
    "Reserves & Surplus": "Capital Account",
    "Current Liabilities": None,
    "Duties & Taxes": "Current Liabilities",
    "Provisions": "Current Liabilities",
    "Sundry Creditors": "Current Liabilities",
    "Loans (Liability)": None,
    "Bank OD A/c": "Loans (Liability)",
    "Secured Loans": "Loans (Liability)",
    "Unsecured Loans": "Loans (Liability)",
    "Suspense A/c": None,
    "Direct Expenses": None,
    "Indirect Expenses": None,
    "Purchase Accounts": None,
    "Direct Incomes": None,
    "Indirect Incomes": None,
    "Sales Accounts": None,
}


def upgrade() -> None:
    op.create_table(
        "ledger_groups",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("tally_group_type", sa.String(), nullable=False),
        sa.Column("parent_group_id", GUID(), sa.ForeignKey("ledger_groups.id"), nullable=True),
    )

    ledger_created_via_enum = sa.Enum("SEED", "RULE", "AI", "MANUAL", name="ledgercreatedvia")
    ledger_created_via_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ledgers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("group_id", GUID(), sa.ForeignKey("ledger_groups.id"), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence_baseline", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_via", ledger_created_via_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- seed the 28 standard groups ---
    group_ids = {name: str(uuid.uuid4()) for name in _GROUP_TREE}
    ledger_groups_table = sa.table(
        "ledger_groups",
        sa.column("id", GUID()),
        sa.column("name", sa.String()),
        sa.column("tally_group_type", sa.String()),
        sa.column("parent_group_id", GUID()),
    )
    op.bulk_insert(
        ledger_groups_table,
        [
            {
                "id": group_ids[name],
                "name": name,
                "tally_group_type": name,
                "parent_group_id": group_ids[parent] if parent else None,
            }
            for name, parent in _GROUP_TREE.items()
        ],
    )

    # --- seed the "Cash" default ledger (the only one of Tally's 2 default ledgers
    # actually used by this system's rule engine; "Profit & Loss A/c" is a Tally
    # system ledger outside this project's Statement-to-Ledger scope) ---
    import datetime

    ledgers_table = sa.table(
        "ledgers",
        sa.column("id", GUID()),
        sa.column("name", sa.String()),
        sa.column("group_id", GUID()),
        sa.column("usage_count", sa.Integer()),
        sa.column("confidence_baseline", sa.Integer()),
        sa.column("created_via", ledger_created_via_enum),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        ledgers_table,
        [
            {
                "id": str(uuid.uuid4()),
                "name": "Cash",
                "group_id": group_ids["Cash-in-Hand"],
                "usage_count": 0,
                "confidence_baseline": 100,
                "created_via": "SEED",
                "created_at": datetime.datetime.now(datetime.timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("ledgers")
    sa.Enum(name="ledgercreatedvia").drop(op.get_bind(), checkfirst=True)
    op.drop_table("ledger_groups")
