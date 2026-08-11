import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID

_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class ResolutionSource(str, enum.Enum):
    RULE = "RULE"
    EXACT_MATCH = "EXACT_MATCH"
    ALIAS_MATCH = "ALIAS_MATCH"
    SIMILARITY_MATCH = "SIMILARITY_MATCH"
    AI_PREDICTION = "AI_PREDICTION"
    MANUAL = "MANUAL"
    AI_FAILED = "AI_FAILED"


class ParsedTransaction(Base):
    __tablename__ = "parsed_transactions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    processing_job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("processing_jobs.id"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    original_narration: Mapped[str] = mapped_column(String, nullable=False)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Module 5 (Normalizer) output. Plain nullable columns, populated after parsing;
    # transaction_type_tag is a free string (not a DB enum) so new categories can be
    # added without a migration.
    normalized_narration: Mapped[str | None] = mapped_column(String, nullable=True)
    transaction_type_tag: Mapped[str | None] = mapped_column(String, nullable=True)

    # Module 6+ (Rule Engine / Ledger Matching / AI) resolution output.
    ledger_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("ledgers.id"), nullable=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("ledger_groups.id"), nullable=True
    )
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_source: Mapped[ResolutionSource | None] = mapped_column(
        Enum(ResolutionSource), nullable=True
    )
    # Module 14 (Voucher Generator) output - the assigned type; the generated
    # voucher document itself (number + narration) lives in the 1:1 `vouchers` row.
    voucher_type_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("voucher_types.id"), nullable=True
    )
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Top similarity-match candidates below the auto-accept threshold, kept for the
    # (future) AI stage and manual review UI so a below-threshold match is never
    # silently discarded. List of {"ledger_id", "ledger_name", "score"}.
    similar_candidates: Mapped[list | None] = mapped_column(_JSON_TYPE, nullable=True)

    # Module 11 (Validation) output.
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("parsed_transactions.id"), nullable=True
    )
    validation_errors: Mapped[list | None] = mapped_column(_JSON_TYPE, nullable=True)

    # Module 12 (Manual Review) output.
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
