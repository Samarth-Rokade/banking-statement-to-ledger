import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.ai.ledger_predictor import LedgerPredictor
from app.database import SessionLocal
from app.jobs import signals
from app.matcher.alias_matcher import AliasMatcher
from app.matcher.exact_matcher import ExactMatcher
from app.matcher.similarity_matcher import SimilarityMatcher
from app.models.processing_job import JobStatus, ProcessingJob
from app.normalizer.narration_normalizer import classify
from app.parser.base import ParserError
from app.parser.factory import get_parser
from app.repositories.parsed_transaction_repository import ParsedTransactionRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.rules.rule_engine import RuleEngine
from app.upload.storage import get_file_storage
from app.validator.validation_engine import ValidationEngine
from app.vouchers.voucher_generator import VoucherGenerator

logger = logging.getLogger(__name__)


def _append_status(job: ProcessingJob, status: JobStatus) -> None:
    now = datetime.now(timezone.utc)
    # Reassign (rather than .append) so SQLAlchemy's change tracking picks up the mutation
    # on this plain JSON column.
    job.status_history = [*job.status_history, {"status": status.value, "timestamp": now.isoformat()}]
    job.status = status


def _claim_next_job(db: Session, from_status: JobStatus, to_status: JobStatus) -> ProcessingJob | None:
    """Atomically claim the oldest job in `from_status` by flipping it to `to_status`.

    The conditional WHERE clause guards against two workers claiming the same row;
    this is sufficient for a single-instance dev worker. A production multi-worker
    deployment on Postgres should additionally use `SELECT ... FOR UPDATE SKIP LOCKED`
    to avoid workers blocking on each other's in-flight claims.
    """
    candidate = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.status == from_status)
        .order_by(ProcessingJob.created_at.asc())
        .first()
    )
    if candidate is None:
        return None

    now = datetime.now(timezone.utc)
    values = {
        "status": to_status,
        "status_history": [
            *candidate.status_history,
            {"status": to_status.value, "timestamp": now.isoformat()},
        ],
    }
    if from_status == JobStatus.QUEUED:
        values["started_at"] = now

    result = db.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == candidate.id, ProcessingJob.status == from_status)
        .values(**values)
    )
    db.commit()
    if result.rowcount == 0:
        return None  # another worker claimed it first
    db.refresh(candidate)
    return candidate


def claim_next_queued_job(db: Session) -> ProcessingJob | None:
    return _claim_next_job(db, JobStatus.QUEUED, JobStatus.PARSING)


def claim_next_normalizing_job(db: Session) -> ProcessingJob | None:
    return _claim_next_job(db, JobStatus.NORMALIZING, JobStatus.MATCHING)


def claim_next_matching_job(db: Session) -> ProcessingJob | None:
    return _claim_next_job(db, JobStatus.MATCHING, JobStatus.AI_PREDICTING)


def claim_next_ai_predicting_job(db: Session) -> ProcessingJob | None:
    return _claim_next_job(db, JobStatus.AI_PREDICTING, JobStatus.VALIDATING)


def claim_next_validating_job(db: Session) -> ProcessingJob | None:
    # REVIEW_REQUIRED is the conservative default target; apply_validation_job
    # overrides to READY on the success path when nothing actually needs review.
    return _claim_next_job(db, JobStatus.VALIDATING, JobStatus.REVIEW_REQUIRED)


def process_job(db: Session, job: ProcessingJob) -> None:
    uploaded_file = UploadedFileRepository(db).get_by_id(job.uploaded_file_id)
    if uploaded_file is None:
        _append_status(job, JobStatus.FAILED)
        job.error_message = "Uploaded file record is missing."
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return

    try:
        content = get_file_storage().read(uploaded_file.storage_path)
        rows = get_parser(uploaded_file.file_type).parse(content)
    except ParserError as exc:
        _append_status(job, JobStatus.FAILED)
        job.error_message = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %s failed during parsing: %s", job.id, exc)
        return
    except Exception as exc:
        # Broad on purpose: storage.read() can fail for reasons specific to
        # whichever backend is configured (a missing local file, a GCS auth/network
        # error, a deleted blob) - none of those should crash the whole worker loop,
        # they should fail just this one job.
        _append_status(job, JobStatus.FAILED)
        job.error_message = f"Could not read the uploaded file: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Job %s failed reading the uploaded file", job.id)
        return

    ParsedTransactionRepository(db).bulk_create(job.id, rows)
    job.total_transactions = len(rows)
    _append_status(job, JobStatus.NORMALIZING)
    db.commit()
    logger.info("Job %s parsed %d transactions", job.id, len(rows))


def normalize_job(db: Session, job: ProcessingJob) -> None:
    """Job status is already MATCHING on entry (set atomically by the claim), since
    Module 6 (Rule Engine) is the next stage to consume it - nothing here re-sets that
    on the success path, only on failure.
    """
    try:
        transactions = ParsedTransactionRepository(db).list_for_job(job.id)
        for txn in transactions:
            normalized_narration, tag = classify(txn.original_narration, txn.debit, txn.credit)
            txn.normalized_narration = normalized_narration
            txn.transaction_type_tag = tag
        db.commit()
    except Exception as exc:
        db.rollback()
        _append_status(job, JobStatus.FAILED)
        job.error_message = f"Normalization failed: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Job %s failed during normalization", job.id)
        return

    logger.info("Job %s normalized %d transactions", job.id, len(transactions))


def apply_ledger_matching_job(db: Session, job: ProcessingJob) -> None:
    """Job status is already AI_PREDICTING on entry (set by the claim); Module 10
    (AI Prediction) is the next stage to consume whatever this waterfall leaves
    unresolved - nothing here re-sets status on the success path, only on failure.

    Runs the deterministic/no-AI waterfall in priority order per transaction, each
    stage only attempted if the previous one didn't resolve it: Rule Engine (Module
    6) -> Exact Match (7) -> Alias Match (8) -> Similarity Match (9).
    """
    try:
        transactions = ParsedTransactionRepository(db).list_for_job(job.id)
        rule_engine = RuleEngine(db)
        exact_matcher = ExactMatcher(db)
        alias_matcher = AliasMatcher(db)
        similarity_matcher = SimilarityMatcher(db)

        resolved_count = 0
        for txn in transactions:
            resolved = (
                rule_engine.try_resolve(txn)
                or exact_matcher.try_resolve(txn)
                or alias_matcher.try_resolve(txn)
                or similarity_matcher.try_resolve(txn)
            )
            if resolved:
                resolved_count += 1

        job.auto_matched_count = resolved_count
        db.commit()
    except Exception as exc:
        db.rollback()
        _append_status(job, JobStatus.FAILED)
        job.error_message = f"Ledger matching failed: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Job %s failed during ledger matching stage", job.id)
        return

    logger.info(
        "Job %s: ledger matching resolved %d/%d transactions",
        job.id,
        resolved_count,
        len(transactions),
    )


def apply_ai_prediction_job(db: Session, job: ProcessingJob) -> None:
    """Job status is already VALIDATING on entry (set by the claim); Module 11
    (Validation) is the next stage - nothing here re-sets status on the success
    path, only on failure. Only ever runs on transactions the deterministic
    waterfall (Modules 6-9) left unresolved.
    """
    try:
        transactions = ParsedTransactionRepository(db).list_for_job(job.id)
        unresolved = [t for t in transactions if t.ledger_id is None]
        resolved_count = LedgerPredictor(db).predict_and_resolve(unresolved)
        job.ai_predicted_count = resolved_count
        db.commit()
    except Exception as exc:
        db.rollback()
        _append_status(job, JobStatus.FAILED)
        job.error_message = f"AI prediction failed: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Job %s failed during AI prediction stage", job.id)
        return

    logger.info(
        "Job %s: AI resolved %d/%d unresolved transactions",
        job.id,
        resolved_count,
        len(unresolved),
    )


def apply_validation_job(db: Session, job: ProcessingJob) -> None:
    """Job status is already REVIEW_REQUIRED on entry (set by the claim), which is
    the conservative default; overridden to READY below when nothing actually
    needs review. Runs Module 11 (Validation) then Module 14 (Voucher Generator -
    every resolved transaction gets a voucher type + number here, whether or not it
    still requires review) - this is the last automated stage before Module 12
    (Manual Review) picks up anything left in REVIEW_REQUIRED.
    """
    try:
        transactions = ParsedTransactionRepository(db).list_for_job(job.id)
        ValidationEngine(db).validate_job_transactions(transactions)
        VoucherGenerator(db).generate_for_job(transactions)

        needs_review = any(t.requires_review or t.ledger_id is None for t in transactions)
        review_count = sum(1 for t in transactions if t.requires_review or t.ledger_id is None)
        job.manual_review_count = review_count
        job.export_ready_count = len(transactions) - review_count

        if not needs_review:
            _append_status(job, JobStatus.READY)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        _append_status(job, JobStatus.FAILED)
        job.error_message = f"Validation failed: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Job %s failed during validation stage", job.id)
        return

    logger.info(
        "Job %s: validation complete, %d/%d transactions need review (status=%s)",
        job.id,
        review_count,
        len(transactions),
        job.status,
    )


def run_once() -> bool:
    """Claim and process a single job across whichever stage has work. Returns False
    if nothing was pending in any stage.
    """
    db = SessionLocal()
    try:
        job = claim_next_queued_job(db)
        if job is not None:
            process_job(db, job)
            return True

        job = claim_next_normalizing_job(db)
        if job is not None:
            normalize_job(db, job)
            return True

        job = claim_next_matching_job(db)
        if job is not None:
            apply_ledger_matching_job(db, job)
            return True

        job = claim_next_ai_predicting_job(db)
        if job is not None:
            apply_ai_prediction_job(db, job)
            return True

        job = claim_next_validating_job(db)
        if job is not None:
            apply_validation_job(db, job)
            return True

        return False
    finally:
        db.close()


def run_worker_loop(poll_interval_seconds: float = 2.0) -> None:
    """Runs until `signals.stop_event` is set. Idle waits are interruptible via
    `signals.wake_event` (set by e.g. the upload endpoint right after creating a
    job) so new work starts immediately instead of waiting out the poll interval -
    the interval is now just a fallback safety net, not the only way work gets
    noticed.
    """
    logger.info("Statement processing worker started (poll interval=%ss)", poll_interval_seconds)
    while not signals.stop_event.is_set():
        processed = run_once()
        if not processed and not signals.stop_event.is_set():
            signals.wake_event.wait(timeout=poll_interval_seconds)
            signals.wake_event.clear()
    logger.info("Statement processing worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker_loop()
