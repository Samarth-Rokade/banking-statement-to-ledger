import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID


class Voucher(Base):
    """Module 14 output: the generated voucher document for a resolved transaction,
    1:1 with parsed_transactions. voucher_number is assigned once and never reused,
    even if the transaction's voucher_type later changes on manual correction - it's
    the stable reference an exported Tally entry is identified by.
    """

    __tablename__ = "vouchers"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    parsed_transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("parsed_transactions.id"), unique=True, nullable=False
    )
    voucher_type_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("voucher_types.id"), nullable=False
    )
    voucher_number: Mapped[str] = mapped_column(String, nullable=False)
    narration: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
