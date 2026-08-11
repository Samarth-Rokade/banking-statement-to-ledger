import uuid

from sqlalchemy.orm import Session

from app.models.ai_prediction import AIPrediction


class AIPredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        parsed_transaction_id: uuid.UUID,
        prompt_name: str,
        model_used: str,
        raw_request: dict,
        raw_response: dict | None,
        predicted_confidence: int | None,
        latency_ms: int,
    ) -> AIPrediction:
        row = AIPrediction(
            parsed_transaction_id=parsed_transaction_id,
            prompt_name=prompt_name,
            model_used=model_used,
            raw_request=raw_request,
            raw_response=raw_response,
            predicted_confidence=predicted_confidence,
            latency_ms=latency_ms,
        )
        self.db.add(row)
        self.db.commit()
        return row
