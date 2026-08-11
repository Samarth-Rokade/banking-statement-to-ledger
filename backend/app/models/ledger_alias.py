import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID


class LedgerAliasSource(str, enum.Enum):
    MANUAL = "MANUAL"
    LEARNED = "LEARNED"


class LedgerAlias(Base):
    __tablename__ = "ledger_aliases"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    ledger_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("ledgers.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[LedgerAliasSource] = mapped_column(
        Enum(LedgerAliasSource), nullable=False, default=LedgerAliasSource.MANUAL
    )
