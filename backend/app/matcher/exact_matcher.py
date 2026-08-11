from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.repositories.ledger_repository import LedgerRepository


class ExactMatcher:
    """Module 7: does a ledger already exist whose name exactly matches the
    normalized narration? No AI, no fuzziness - a straight lookup.
    """

    def __init__(self, db: Session):
        self.ledger_repo = LedgerRepository(db)

    def try_resolve(self, transaction: ParsedTransaction) -> bool:
        if not transaction.normalized_narration:
            return False

        ledger = self.ledger_repo.get_by_name(transaction.normalized_narration)
        if ledger is None:
            return False

        self.ledger_repo.increment_usage(ledger)
        transaction.ledger_id = ledger.id
        transaction.group_id = ledger.group_id
        transaction.confidence = 100
        transaction.resolution_source = ResolutionSource.EXACT_MATCH
        transaction.requires_review = False
        return True
