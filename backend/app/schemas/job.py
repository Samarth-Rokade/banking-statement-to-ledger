import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.processing_job import JobStatus


class StatusHistoryEntry(BaseModel):
    status: JobStatus
    timestamp: datetime


class ProcessingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    uploaded_file_id: uuid.UUID
    status: JobStatus
    status_history: list[StatusHistoryEntry]
    total_transactions: int
    auto_matched_count: int
    ai_predicted_count: int
    manual_review_count: int
    export_ready_count: int
    error_message: str | None
    created_at: datetime


class UploadResponse(BaseModel):
    job_id: uuid.UUID


class ProcessingJobListResponse(BaseModel):
    items: list[ProcessingJobOut]
    total: int
    page: int
    page_size: int
