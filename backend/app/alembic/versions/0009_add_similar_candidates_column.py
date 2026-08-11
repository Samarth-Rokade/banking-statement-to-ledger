"""add similar_candidates column to parsed_transactions

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    similar_candidates_type = sa.JSON().with_variant(JSONB(), "postgresql")
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.add_column(sa.Column("similar_candidates", similar_candidates_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("parsed_transactions") as batch_op:
        batch_op.drop_column("similar_candidates")
