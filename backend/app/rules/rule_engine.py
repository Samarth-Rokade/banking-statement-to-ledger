from sqlalchemy.orm import Session

from app.models.ledger import LedgerCreatedVia
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.repositories.ledger_repository import LedgerRepository
from app.repositories.rule_repository import RuleRepository


class RuleEngine:
    """Module 6: deterministic tag -> ledger/group mapping. No AI, no similarity
    matching - only resolves transactions whose transaction_type_tag alone implies a
    fixed ledger regardless of counterparty (CASH_DEPOSIT, ATM, BANK_CHARGES,
    INTEREST). Anything else (RTGS/NEFT/IMPS/CHEQUE_*/UPI_QR_SETTLEMENT/OTHER) is left
    untouched for the exact/alias/similarity/AI stages to attempt.
    """

    def __init__(self, db: Session):
        self.db = db
        self.rule_repo = RuleRepository(db)
        self.ledger_repo = LedgerRepository(db)

    def try_resolve(self, transaction: ParsedTransaction) -> bool:
        if not transaction.transaction_type_tag:
            return False

        is_debit = transaction.debit > 0
        rule = self.rule_repo.find_matching_tag_rule(transaction.transaction_type_tag, is_debit)
        if rule is None or not rule.ledger_name or not rule.group_name:
            return False

        ledger = self.ledger_repo.get_or_create(
            rule.ledger_name, rule.group_name, created_via=LedgerCreatedVia.RULE
        )
        self.ledger_repo.increment_usage(ledger)

        transaction.ledger_id = ledger.id
        transaction.group_id = ledger.group_id
        transaction.confidence = 100
        transaction.resolution_source = ResolutionSource.RULE
        transaction.requires_review = False
        return True

    def resolve_job_transactions(self, transactions: list[ParsedTransaction]) -> int:
        return sum(1 for txn in transactions if self.try_resolve(txn))
