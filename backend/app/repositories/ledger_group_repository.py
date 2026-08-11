from sqlalchemy.orm import Session

from app.models.ledger_group import LedgerGroup


class LedgerGroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, group_id) -> LedgerGroup | None:
        return self.db.get(LedgerGroup, group_id)

    def get_by_name(self, name: str) -> LedgerGroup | None:
        return self.db.query(LedgerGroup).filter(LedgerGroup.name == name).first()

    def list_all(self) -> list[LedgerGroup]:
        return self.db.query(LedgerGroup).order_by(LedgerGroup.name).all()
