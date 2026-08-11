from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.repositories.ledger_alias_repository import LedgerAliasRepository
from app.repositories.ledger_repository import LedgerRepository

# Aliases are deterministic once recorded (either a human confirmed the mapping, or
# it was learned from a prior manual correction of the exact same narration variant),
# so this is as trustworthy as an exact match - not quite 100 because an alias could
# in principle have drifted (e.g. the ledger it points to was later renamed/merged).
ALIAS_MATCH_CONFIDENCE = 98


class AliasMatcher:
    """Module 8: has this narration variant been seen before and mapped to a ledger,
    either manually (Module 7 UI) or learned from a past manual correction
    (Module 13, once it exists)?
    """

    def __init__(self, db: Session):
        self.alias_repo = LedgerAliasRepository(db)
        self.ledger_repo = LedgerRepository(db)

    def try_resolve(self, transaction: ParsedTransaction) -> bool:
        if not transaction.normalized_narration:
            return False

        alias = self.alias_repo.get_by_alias(transaction.normalized_narration)
        if alias is None:
            return False

        ledger = self.ledger_repo.get_by_id(alias.ledger_id)
        if ledger is None:
            return False

        self.ledger_repo.increment_usage(ledger)
        transaction.ledger_id = ledger.id
        transaction.group_id = ledger.group_id
        transaction.confidence = ALIAS_MATCH_CONFIDENCE
        transaction.resolution_source = ResolutionSource.ALIAS_MATCH
        transaction.requires_review = False
        return True
