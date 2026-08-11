import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID

_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class AIPrediction(Base):
    """Append-only audit trail: every Gemini call, regardless of outcome. Never
    updated after insert - this is what makes Module 13 (Learning) and future prompt
    tuning possible.
    """

    __tablename__ = "ai_predictions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    parsed_transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("parsed_transactions.id"), nullable=False
    )
    prompt_name: Mapped[str] = mapped_column(String, nullable=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False)
    raw_request: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)
    raw_response: Mapped[dict | None] = mapped_column(_JSON_TYPE, nullable=True)
    predicted_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
