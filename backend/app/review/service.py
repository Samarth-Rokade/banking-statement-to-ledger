import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning.service import record_correction
from app.models.ledger import Ledger
from app.models.manual_correction import CorrectionField
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.models.processing_job import JobStatus, ProcessingJob
from app.repositories.ledger_repository import LedgerRepository
from app.repositories.manual_correction_repository import ManualCorrectionRepository
from app.repositories.parsed_transaction_repository import ParsedTransactionRepository
from app.vouchers.voucher_generator import VoucherGenerator


class ReviewError(ValueError):
    """Raised for a review action that can't be applied as requested; the router
    translates this into a 400.
    """


def _append_status(job: ProcessingJob, status: JobStatus) -> None:
    now = datetime.now(timezone.utc)
    job.status_history = [*job.status_history, {"status": status.value, "timestamp": now.isoformat()}]
    job.status = status


def _refresh_job_after_review(db: Session, job: ProcessingJob) -> None:
    """Recomputes the job's review counters and, if this was the last row still
    needing attention, advances a REVIEW_REQUIRED job to READY. Mirrors the same
    "needs review" definition Module 11's apply_validation_job used.
    """
    transactions = ParsedTransactionRepository(db).list_for_job(job.id)
    review_count = sum(1 for t in transactions if t.requires_review or t.ledger_id is None)
    job.manual_review_count = review_count
    job.export_ready_count = len(transactions) - review_count

    if review_count == 0 and job.status == JobStatus.REVIEW_REQUIRED:
        _append_status(job, JobStatus.READY)
        job.completed_at = datetime.now(timezone.utc)


def _mark_reviewed(txn: ParsedTransaction, user_id: uuid.UUID) -> None:
    txn.requires_review = False
    txn.confidence = 100
    txn.resolution_source = ResolutionSource.MANUAL
    txn.reviewed_by_user_id = user_id
    txn.reviewed_at = datetime.now(timezone.utc)


def approve_transaction(db: Session, txn: ParsedTransaction, user_id: uuid.UUID) -> None:
    if txn.ledger_id is None:
        raise ReviewError("Cannot approve a transaction with no ledger assigned yet.")

    _mark_reviewed(txn, user_id)
    record_correction(db, txn, txn.ledger_id)
    VoucherGenerator(db).generate_for_transaction(txn)
    job = db.get(ProcessingJob, txn.processing_job_id)
    _refresh_job_after_review(db, job)
    db.commit()


def patch_transaction(
    db: Session, txn: ParsedTransaction, ledger_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    ledger = LedgerRepository(db).get_by_id(ledger_id)
    if ledger is None:
        raise ReviewError("Ledger not found.")

    old_ledger = db.get(Ledger, txn.ledger_id) if txn.ledger_id else None
    if old_ledger is not None and old_ledger.id != ledger.id:
        ManualCorrectionRepository(db).create(
            parsed_transaction_id=txn.id,
            user_id=user_id,
            field_changed=CorrectionField.LEDGER,
            old_value=old_ledger.name,
            new_value=ledger.name,
        )
    elif old_ledger is None:
        ManualCorrectionRepository(db).create(
            parsed_transaction_id=txn.id,
            user_id=user_id,
            field_changed=CorrectionField.LEDGER,
            old_value=None,
            new_value=ledger.name,
        )

    txn.ledger_id = ledger.id
    txn.group_id = ledger.group_id
    txn.validation_errors = None
    _mark_reviewed(txn, user_id)
    record_correction(db, txn, ledger.id)
    VoucherGenerator(db).generate_for_transaction(txn)

    job = db.get(ProcessingJob, txn.processing_job_id)
    _refresh_job_after_review(db, job)
    db.commit()


def mark_duplicate(
    db: Session,
    txn: ParsedTransaction,
    is_duplicate: bool,
    duplicate_of_transaction_id: uuid.UUID | None,
    user_id: uuid.UUID,
) -> None:
    txn.is_duplicate = is_duplicate
    txn.duplicate_of_transaction_id = duplicate_of_transaction_id if is_duplicate else None
    txn.requires_review = False
    txn.reviewed_by_user_id = user_id
    txn.reviewed_at = datetime.now(timezone.utc)

    job = db.get(ProcessingJob, txn.processing_job_id)
    _refresh_job_after_review(db, job)
    db.commit()
