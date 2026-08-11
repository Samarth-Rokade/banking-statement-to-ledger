import uuid

from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction
from app.repositories.ledger_alias_repository import LedgerAliasRepository
from app.repositories.ledger_repository import LedgerRepository


def record_correction(db: Session, txn: ParsedTransaction, ledger_id: uuid.UUID) -> None:
    """Module 13: every human-confirmed narration -> ledger mapping (an approval or
    an edit in Module 12) is remembered as a LEARNED alias, so the next transaction
    with this exact normalized narration resolves deterministically via Module 8
    (Alias Match) instead of ever reaching the AI stage again.
    """
    if not txn.normalized_narration:
        return

    ledger = LedgerRepository(db).get_by_id(ledger_id)
    if ledger is None or ledger.name == txn.normalized_narration:
        # An exact ledger-name match is already covered by Module 7 (Exact Match) -
        # an alias here would just be a redundant row.
        return

    LedgerAliasRepository(db).upsert_learned(txn.normalized_narration, ledger_id)
