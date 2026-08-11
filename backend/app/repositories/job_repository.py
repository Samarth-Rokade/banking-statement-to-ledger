import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.processing_job import JobStatus, ProcessingJob
from app.models.uploaded_file import UploadedFile


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, uploaded_file_id: uuid.UUID) -> ProcessingJob:
        now = datetime.now(timezone.utc)
        job = ProcessingJob(
            uploaded_file_id=uploaded_file_id,
            status=JobStatus.QUEUED,
            status_history=[{"status": JobStatus.QUEUED.value, "timestamp": now.isoformat()}],
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_by_id_for_user(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProcessingJob | None:
        stmt = (
            select(ProcessingJob)
            .join(UploadedFile, ProcessingJob.uploaded_file_id == UploadedFile.id)
            .where(ProcessingJob.id == job_id, UploadedFile.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(
        self,
        user_id: uuid.UUID,
        status: JobStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ProcessingJob], int]:
        base_stmt = (
            select(ProcessingJob)
            .join(UploadedFile, ProcessingJob.uploaded_file_id == UploadedFile.id)
            .where(UploadedFile.user_id == user_id)
        )
        if status is not None:
            base_stmt = base_stmt.where(ProcessingJob.status == status)

        total = self.db.execute(
            select(func.count()).select_from(base_stmt.subquery())
        ).scalar_one()

        items_stmt = (
            base_stmt.order_by(ProcessingJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total
