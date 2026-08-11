import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.models.processing_job import ProcessingJob
from app.models.uploaded_file import UploadedFile
from app.parser.base import TransactionRow


class ParsedTransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_create(
        self, processing_job_id: uuid.UUID, rows: list[TransactionRow]
    ) -> list[ParsedTransaction]:
        transactions = [
            ParsedTransaction(
                processing_job_id=processing_job_id,
                row_number=row.row_number,
                txn_date=row.txn_date,
                original_narration=row.description,
                reference=row.reference,
                debit=row.debit,
                credit=row.credit,
                balance=row.balance,
            )
            for row in rows
        ]
        self.db.add_all(transactions)
        self.db.commit()
        return transactions

    def list_for_job(self, processing_job_id: uuid.UUID) -> list[ParsedTransaction]:
        stmt = (
            select(ParsedTransaction)
            .where(ParsedTransaction.processing_job_id == processing_job_id)
            .order_by(ParsedTransaction.row_number)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, transaction_id: uuid.UUID) -> ParsedTransaction | None:
        return self.db.get(ParsedTransaction, transaction_id)

    def get_by_id_for_user(
        self, transaction_id: uuid.UUID, user_id: uuid.UUID
    ) -> ParsedTransaction | None:
        stmt = (
            select(ParsedTransaction)
            .join(ProcessingJob, ParsedTransaction.processing_job_id == ProcessingJob.id)
            .join(UploadedFile, ProcessingJob.uploaded_file_id == UploadedFile.id)
            .where(ParsedTransaction.id == transaction_id, UploadedFile.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_job_paginated(
        self,
        processing_job_id: uuid.UUID,
        requires_review: bool | None,
        resolution_source: ResolutionSource | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ParsedTransaction], int]:
        base_stmt = select(ParsedTransaction).where(
            ParsedTransaction.processing_job_id == processing_job_id
        )
        if requires_review is not None:
            base_stmt = base_stmt.where(ParsedTransaction.requires_review == requires_review)
        if resolution_source is not None:
            base_stmt = base_stmt.where(ParsedTransaction.resolution_source == resolution_source)

        total = self.db.execute(
            select(func.count()).select_from(base_stmt.subquery())
        ).scalar_one()

        items_stmt = (
            base_stmt.order_by(ParsedTransaction.row_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total
