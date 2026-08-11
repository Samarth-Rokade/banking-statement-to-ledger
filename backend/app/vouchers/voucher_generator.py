from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction
from app.models.voucher import Voucher
from app.repositories.ledger_group_repository import LedgerGroupRepository
from app.repositories.voucher_repository import VoucherRepository
from app.repositories.voucher_type_repository import VoucherTypeRepository

# A ledger whose own group is one of these represents the entity's own cash/bank -
# so a transaction resolved against it is a transfer between the entity's own
# accounts (e.g. an ATM withdrawal or cash deposit), not a real Receipt/Payment.
_CONTRA_GROUPS = {"Bank Accounts", "Cash-in-Hand"}

_VOUCHER_NUMBER_PREFIX = "V"


def determine_voucher_type_name(group_name: str, debit, credit) -> str:
    """Deterministic per Module 14: for a bank-statement-derived transaction, the
    voucher type is fully determined by the resolved ledger's group plus the
    debit/credit direction Module 11 already guarantees is unambiguous (exactly one
    of debit/credit is positive) - there is no genuine residual case here for Gemini
    to resolve, unlike ledger prediction.
    """
    if group_name in _CONTRA_GROUPS:
        return "Contra"
    if credit and credit > 0:
        return "Receipt"
    if debit and debit > 0:
        return "Payment"
    return "Journal"  # unreachable given Module 11's debit/credit validation, kept as a safe fallback


class VoucherGenerator:
    """Module 14: assigns a voucher type to every resolved transaction and
    generates its 1:1 voucher document (a stable, sequential voucher_number plus
    the narration that will be written to the export).
    """

    def __init__(self, db: Session):
        self.db = db
        self.group_repo = LedgerGroupRepository(db)
        self.voucher_type_repo = VoucherTypeRepository(db)
        self.voucher_repo = VoucherRepository(db)

    def generate_for_transaction(self, txn: ParsedTransaction) -> Voucher | None:
        if txn.ledger_id is None or txn.group_id is None:
            return None  # nothing to generate yet - still unresolved

        group = self.group_repo.get_by_id(txn.group_id)
        if group is None:
            return None  # dangling group reference - Module 11 will have already flagged this

        voucher_type_name = determine_voucher_type_name(group.name, txn.debit, txn.credit)
        voucher_type = self.voucher_type_repo.get_by_name(voucher_type_name)
        txn.voucher_type_id = voucher_type.id

        narration = txn.normalized_narration or txn.original_narration
        existing = self.voucher_repo.get_by_transaction_id(txn.id)
        if existing is not None:
            existing.voucher_type_id = voucher_type.id
            existing.narration = narration
            return existing

        next_seq = self.voucher_repo.count_for_job(txn.processing_job_id) + 1
        voucher_number = f"{_VOUCHER_NUMBER_PREFIX}{next_seq:05d}"
        return self.voucher_repo.create(txn.id, voucher_type.id, voucher_number, narration)

    def generate_for_job(self, transactions: list[ParsedTransaction]) -> int:
        generated = 0
        for txn in transactions:
            if self.generate_for_transaction(txn) is not None:
                generated += 1
        return generated
