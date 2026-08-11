import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction
from app.models.voucher import Voucher


class VoucherRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_transaction_id(self, parsed_transaction_id: uuid.UUID) -> Voucher | None:
        return (
            self.db.query(Voucher)
            .filter(Voucher.parsed_transaction_id == parsed_transaction_id)
            .first()
        )

    def count_for_job(self, processing_job_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Voucher)
            .join(ParsedTransaction, Voucher.parsed_transaction_id == ParsedTransaction.id)
            .where(ParsedTransaction.processing_job_id == processing_job_id)
        )
        return self.db.execute(stmt).scalar_one()

    def create(
        self,
        parsed_transaction_id: uuid.UUID,
        voucher_type_id: uuid.UUID,
        voucher_number: str,
        narration: str,
    ) -> Voucher:
        voucher = Voucher(
            parsed_transaction_id=parsed_transaction_id,
            voucher_type_id=voucher_type_id,
            voucher_number=voucher_number,
            narration=narration,
        )
        self.db.add(voucher)
        # Flushed (not committed) so a subsequent count_for_job() call later in the
        # same generate_for_job() loop sees this row - autoflush is off in tests.
        self.db.flush()
        return voucher
