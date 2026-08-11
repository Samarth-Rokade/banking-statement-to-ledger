from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction
from app.repositories.ledger_group_repository import LedgerGroupRepository
from app.repositories.ledger_repository import LedgerRepository

# Small tolerance for rounding drift between what the parser extracted and what the
# bank's own running balance shows; not zero, since PDF-extracted amounts can carry
# a paisa of float/rounding noise.
BALANCE_TOLERANCE = Decimal("0.01")


def _validate_ledger_group_consistency(
    txn: ParsedTransaction, ledger_repo: LedgerRepository, group_repo: LedgerGroupRepository
) -> list[str]:
    if txn.ledger_id is None:
        return []  # still unresolved - not this check's concern, Module 12 handles it

    errors: list[str] = []
    ledger = ledger_repo.get_by_id(txn.ledger_id)
    if ledger is None:
        errors.append("Assigned ledger no longer exists.")
        return errors

    group = group_repo.get_by_id(txn.group_id) if txn.group_id else None
    if group is None:
        errors.append("Assigned ledger group no longer exists.")
    elif ledger.group_id != txn.group_id:
        errors.append("Transaction's group does not match its ledger's actual group.")

    return errors


def _validate_debit_credit(txn: ParsedTransaction) -> list[str]:
    if txn.debit > 0 and txn.credit > 0:
        return ["Transaction has both a debit and a credit amount."]
    if txn.debit == 0 and txn.credit == 0:
        return ["Transaction has neither a debit nor a credit amount."]
    return []


def _validate_running_balances(transactions: list[ParsedTransaction]) -> dict:
    """Cross-checks each row's own balance against the previous row's balance plus
    this row's net amount - catches parser extraction errors that the amounts alone
    wouldn't reveal. A no-op whenever the statement's balance column wasn't
    available to begin with (every txn.balance is then None).
    """
    errors_by_id: dict = {}
    ordered = sorted(transactions, key=lambda t: t.row_number)
    previous: ParsedTransaction | None = None
    for txn in ordered:
        if previous is not None and previous.balance is not None and txn.balance is not None:
            expected = previous.balance + txn.credit - txn.debit
            if abs(expected - txn.balance) > BALANCE_TOLERANCE:
                errors_by_id.setdefault(txn.id, []).append(
                    f"Balance does not follow from the previous row "
                    f"(expected {expected}, statement shows {txn.balance})."
                )
        previous = txn
    return errors_by_id


def _detect_duplicates(transactions: list[ParsedTransaction]) -> None:
    """Flags exact repeats (same date, debit, credit, narration) within this job.
    Cross-job duplicate detection (e.g. the same statement re-uploaded) is a known
    follow-up, not implemented yet.
    """
    seen: dict[tuple, ParsedTransaction] = {}
    for txn in sorted(transactions, key=lambda t: t.row_number):
        key = (txn.txn_date, txn.debit, txn.credit, txn.original_narration)
        first = seen.get(key)
        if first is None:
            seen[key] = txn
            continue
        txn.is_duplicate = True
        txn.duplicate_of_transaction_id = first.id


class ValidationEngine:
    """Module 11: the last automated check before a job is either marked READY or
    routed to manual review. Runs after AI Prediction (Module 10) so it has every
    transaction's final resolution state to check. "Voucher exists" (per the spec's
    validation checklist) is deferred until Module 14 (Voucher Generator) exists -
    there's nothing to validate yet.
    """

    def __init__(self, db: Session):
        self.ledger_repo = LedgerRepository(db)
        self.group_repo = LedgerGroupRepository(db)

    def validate_job_transactions(self, transactions: list[ParsedTransaction]) -> None:
        _detect_duplicates(transactions)
        balance_errors = _validate_running_balances(transactions)

        for txn in transactions:
            errors: list[str] = []
            errors.extend(_validate_ledger_group_consistency(txn, self.ledger_repo, self.group_repo))
            errors.extend(_validate_debit_credit(txn))
            errors.extend(balance_errors.get(txn.id, []))
            if txn.is_duplicate:
                errors.append("Possible duplicate of an earlier row in this statement.")

            if not errors:
                continue

            txn.validation_errors = errors
            txn.requires_review = True
            if any("no longer exists" in e or "does not match" in e for e in errors):
                # A broken ledger/group reference is a real resolution failure, not
                # just something to flag - don't let the export trust it.
                txn.confidence = 0
