import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.processing_job import JobStatus
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.job import ProcessingJobListResponse, ProcessingJobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=ProcessingJobListResponse)
def list_jobs(
    status: JobStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcessingJobListResponse:
    items, total = JobRepository(db).list_for_user(current_user.id, status, page, page_size)
    return ProcessingJobListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=ProcessingJobOut)
def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    job = JobRepository(db).get_by_id_for_user(job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
