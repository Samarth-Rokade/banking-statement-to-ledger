from sqlalchemy.orm import Session

from app.models.ledger import Ledger, LedgerCreatedVia
from app.repositories.ledger_group_repository import LedgerGroupRepository


class LedgerRepository:
    def __init__(self, db: Session):
        self.db = db
        self.group_repo = LedgerGroupRepository(db)

    def get_by_id(self, ledger_id) -> Ledger | None:
        return self.db.get(Ledger, ledger_id)

    def get_by_name(self, name: str) -> Ledger | None:
        return self.db.query(Ledger).filter(Ledger.name == name).first()

    def list_all(self, search: str | None = None) -> list[Ledger]:
        query = self.db.query(Ledger)
        if search:
            query = query.filter(Ledger.name.ilike(f"%{search}%"))
        return query.order_by(Ledger.name).all()

    def get_or_create(self, name: str, group_name: str, created_via: LedgerCreatedVia) -> Ledger:
        ledger = self.get_by_name(name)
        if ledger is not None:
            return ledger

        group = self.group_repo.get_by_name(group_name)
        if group is None:
            raise ValueError(f"Ledger group '{group_name}' does not exist")

        ledger = Ledger(name=name, group_id=group.id, created_via=created_via)
        self.db.add(ledger)
        self.db.commit()
        self.db.refresh(ledger)
        return ledger

    def increment_usage(self, ledger: Ledger) -> None:
        ledger.usage_count += 1

    def create_manual(self, name: str, group_id) -> Ledger:
        """Module 7 (Ledger Master UI): a human creating a ledger ahead of time, e.g.
        to pre-populate a counterparty before any statement mentions it.
        """
        if self.get_by_name(name) is not None:
            raise ValueError(f"A ledger named '{name}' already exists.")
        if self.group_repo.get_by_id(group_id) is None:
            raise ValueError("Ledger group not found.")

        ledger = Ledger(name=name, group_id=group_id, created_via=LedgerCreatedVia.MANUAL)
        self.db.add(ledger)
        self.db.commit()
        self.db.refresh(ledger)
        return ledger
