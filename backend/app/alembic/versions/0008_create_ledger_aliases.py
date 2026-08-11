"""create ledger_aliases table

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa

from app.utils.types import GUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source_enum = sa.Enum("MANUAL", "LEARNED", name="ledgeraliassource")
    source_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ledger_aliases",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("ledger_id", GUID(), sa.ForeignKey("ledgers.id"), nullable=False),
        sa.Column("alias", sa.String(), nullable=False, unique=True),
        sa.Column("source", source_enum, nullable=False),
    )
    op.create_index("ix_ledger_aliases_ledger_id", "ledger_aliases", ["ledger_id"])


def downgrade() -> None:
    op.drop_index("ix_ledger_aliases_ledger_id", table_name="ledger_aliases")
    op.drop_table("ledger_aliases")
    sa.Enum(name="ledgeraliassource").drop(op.get_bind(), checkfirst=True)
