import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID

_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    NORMALIZING = "NORMALIZING"
    MATCHING = "MATCHING"
    AI_PREDICTING = "AI_PREDICTING"
    VALIDATING = "VALIDATING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("uploaded_files.id"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.QUEUED
    )
    status_history: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False, default=list)

    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_predicted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manual_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    export_ready_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
