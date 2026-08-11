import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.parsed_transaction import ResolutionSource


class ParsedTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    processing_job_id: uuid.UUID
    row_number: int
    txn_date: date
    original_narration: str
    normalized_narration: str | None
    reference: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal | None
    transaction_type_tag: str | None
    ledger_id: uuid.UUID | None
    group_id: uuid.UUID | None
    confidence: int | None
    resolution_source: ResolutionSource | None
    voucher_type_id: uuid.UUID | None
    similar_candidates: list | None
    requires_review: bool
    is_duplicate: bool
    duplicate_of_transaction_id: uuid.UUID | None
    validation_errors: list | None
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None


class ParsedTransactionListResponse(BaseModel):
    items: list[ParsedTransactionOut]
    total: int
    page: int
    page_size: int


class TransactionPatchRequest(BaseModel):
    # group_id is intentionally not accepted here - it's always derived from the
    # chosen ledger's own group, so a human can never create the exact
    # ledger/group mismatch Module 11's validation engine checks for.
    ledger_id: uuid.UUID


class MarkDuplicateRequest(BaseModel):
    is_duplicate: bool
    duplicate_of_transaction_id: uuid.UUID | None = None
