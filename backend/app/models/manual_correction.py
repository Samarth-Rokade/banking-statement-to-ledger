import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID


class CorrectionField(str, enum.Enum):
    LEDGER = "LEDGER"
    GROUP = "GROUP"
    VOUCHER = "VOUCHER"


class ManualCorrection(Base):
    """Append-only audit trail of every human edit made during Module 12 (Manual
    Review) - never updated after insert. This is what Module 13 (Learning System)
    will read to write new ledger aliases.
    """

    __tablename__ = "manual_corrections"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    parsed_transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("parsed_transactions.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    field_changed: Mapped[CorrectionField] = mapped_column(Enum(CorrectionField), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
