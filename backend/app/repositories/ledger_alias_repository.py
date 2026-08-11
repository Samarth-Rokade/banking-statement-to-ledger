import uuid

from sqlalchemy.orm import Session

from app.models.ledger_alias import LedgerAlias, LedgerAliasSource


class LedgerAliasRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_alias(self, alias: str) -> LedgerAlias | None:
        return self.db.query(LedgerAlias).filter(LedgerAlias.alias == alias).first()

    def list_for_ledger(self, ledger_id: uuid.UUID) -> list[LedgerAlias]:
        return self.db.query(LedgerAlias).filter(LedgerAlias.ledger_id == ledger_id).all()

    def list_all(self) -> list[LedgerAlias]:
        return self.db.query(LedgerAlias).all()

    def create(
        self, ledger_id: uuid.UUID, alias: str, source: LedgerAliasSource
    ) -> LedgerAlias:
        row = LedgerAlias(ledger_id=ledger_id, alias=alias, source=source)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def upsert_learned(self, alias: str, ledger_id: uuid.UUID) -> LedgerAlias:
        """Records a narration -> ledger mapping learned from a human review action.
        A MANUAL alias was set deliberately through the ledger UI (Module 7), so it's
        never overwritten by a learned correction pointing elsewhere - only a
        previously-LEARNED alias gets updated to the freshest mapping.
        """
        existing = self.get_by_alias(alias)
        if existing is None:
            return self.create(ledger_id, alias, LedgerAliasSource.LEARNED)
        if existing.source == LedgerAliasSource.MANUAL:
            return existing
        existing.ledger_id = ledger_id
        self.db.commit()
        self.db.refresh(existing)
        return existing
