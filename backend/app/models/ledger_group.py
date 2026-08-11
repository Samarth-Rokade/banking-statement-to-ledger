import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID


class LedgerGroup(Base):
    __tablename__ = "ledger_groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    tally_group_type: Mapped[str] = mapped_column(String, nullable=False)
    parent_group_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("ledger_groups.id"), nullable=True
    )
