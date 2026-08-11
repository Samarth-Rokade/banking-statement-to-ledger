import uuid

from sqlalchemy.orm import Session

from app.models.voucher_type import VoucherType


class VoucherTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, voucher_type_id: uuid.UUID) -> VoucherType | None:
        return self.db.get(VoucherType, voucher_type_id)

    def get_by_name(self, name: str) -> VoucherType | None:
        return self.db.query(VoucherType).filter(VoucherType.name == name).first()

    def list_all(self) -> list[VoucherType]:
        return self.db.query(VoucherType).order_by(VoucherType.name).all()
