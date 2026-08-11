import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID


class LedgerCreatedVia(str, enum.Enum):
    SEED = "SEED"
    RULE = "RULE"
    AI = "AI"
    MANUAL = "MANUAL"


class Ledger(Base):
    __tablename__ = "ledgers"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("ledger_groups.id"), nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_baseline: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_via: Mapped[LedgerCreatedVia] = mapped_column(
        Enum(LedgerCreatedVia), nullable=False, default=LedgerCreatedVia.MANUAL
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
