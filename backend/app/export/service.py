from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction
from app.models.processing_job import JobStatus, ProcessingJob
from app.repositories.ledger_group_repository import LedgerGroupRepository
from app.repositories.ledger_repository import LedgerRepository
from app.repositories.voucher_repository import VoucherRepository
from app.repositories.voucher_type_repository import VoucherTypeRepository

# Job states in which exporting doesn't make sense yet - still mid-pipeline, or
# already failed.
_NOT_EXPORTABLE_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.PARSING,
    JobStatus.NORMALIZING,
    JobStatus.MATCHING,
    JobStatus.AI_PREDICTING,
    JobStatus.VALIDATING,
    JobStatus.FAILED,
}


class ExportNotReadyError(ValueError):
    """Raised when the job hasn't finished automated processing yet (or failed)."""


class ExportBlockedError(ValueError):
    """Raised when a job has transactions still needing attention and the caller
    didn't explicitly ask to export anyway; the router translates this into a 409.
    """

    def __init__(self, unresolved_count: int, requires_review_count: int):
        self.unresolved_count = unresolved_count
        self.requires_review_count = requires_review_count
        super().__init__(
            f"{unresolved_count} transaction(s) unresolved and "
            f"{requires_review_count} still require review. Pass ?force=true to "
            f"export the remaining ready rows now."
        )


@dataclass
class ExportRow:
    row_number: int
    txn_date: date
    voucher_type: str
    voucher_number: str
    ledger_name: str
    group_name: str
    debit: Decimal
    credit: Decimal
    narration: str


def _is_export_eligible(txn: ParsedTransaction) -> bool:
    return txn.ledger_id is not None and not txn.requires_review and not txn.is_duplicate


def _is_blocking(txn: ParsedTransaction) -> bool:
    # A duplicate is deliberately excluded from export, not "blocking" it - it isn't
    # something the user still needs to resolve before exporting what IS ready.
    return not txn.is_duplicate and (txn.ledger_id is None or txn.requires_review)


def check_job_exportable(job: ProcessingJob) -> None:
    if job.status in _NOT_EXPORTABLE_STATUSES:
        raise ExportNotReadyError(f"Job is {job.status.value.lower()}, not ready to export yet.")


def check_export_readiness(transactions: list[ParsedTransaction], force: bool) -> None:
    if force:
        return

    unresolved_count = sum(1 for t in transactions if _is_blocking(t) and t.ledger_id is None)
    requires_review_count = sum(
        1 for t in transactions if _is_blocking(t) and t.ledger_id is not None
    )
    if unresolved_count or requires_review_count:
        raise ExportBlockedError(unresolved_count, requires_review_count)


def build_export_rows(db: Session, transactions: list[ParsedTransaction]) -> list[ExportRow]:
    """Re-derives export rows straight from current DB state every call - per the
    plan's "re-validated at export time, never trusts stale state" principle, this
    never reads from a cached/previously-generated export.
    """
    ledger_repo = LedgerRepository(db)
    group_repo = LedgerGroupRepository(db)
    voucher_repo = VoucherRepository(db)
    voucher_type_repo = VoucherTypeRepository(db)

    rows: list[ExportRow] = []
    for txn in transactions:
        if not _is_export_eligible(txn):
            continue

        ledger = ledger_repo.get_by_id(txn.ledger_id)
        group = group_repo.get_by_id(txn.group_id) if txn.group_id else None
        voucher = voucher_repo.get_by_transaction_id(txn.id)
        voucher_type = (
            voucher_type_repo.get_by_id(txn.voucher_type_id) if txn.voucher_type_id else None
        )
        if ledger is None or group is None or voucher is None or voucher_type is None:
            # Module 11 already guards against a dangling ledger/group reference, and
            # every eligible (resolved) transaction gets a voucher in Module 14 - this
            # should be unreachable, but skip defensively rather than export garbage.
            continue

        rows.append(
            ExportRow(
                row_number=txn.row_number,
                txn_date=txn.txn_date,
                voucher_type=voucher_type.name,
                voucher_number=voucher.voucher_number,
                ledger_name=ledger.name,
                group_name=group.name,
                debit=txn.debit,
                credit=txn.credit,
                narration=voucher.narration,
            )
        )

    rows.sort(key=lambda r: r.row_number)
    return rows


def mark_exported(db: Session, job: ProcessingJob) -> None:
    if job.status == JobStatus.EXPORTED:
        return  # already marked by an earlier export call - re-downloading is fine
    now = datetime.now(timezone.utc)
    job.status_history = [*job.status_history, {"status": JobStatus.EXPORTED.value, "timestamp": now.isoformat()}]
    job.status = JobStatus.EXPORTED
    db.commit()
