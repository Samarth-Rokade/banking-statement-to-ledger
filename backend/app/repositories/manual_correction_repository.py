import uuid

from sqlalchemy.orm import Session

from app.models.manual_correction import CorrectionField, ManualCorrection


class ManualCorrectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        parsed_transaction_id: uuid.UUID,
        user_id: uuid.UUID,
        field_changed: CorrectionField,
        old_value: str | None,
        new_value: str | None,
    ) -> ManualCorrection:
        correction = ManualCorrection(
            parsed_transaction_id=parsed_transaction_id,
            user_id=user_id,
            field_changed=field_changed,
            old_value=old_value,
            new_value=new_value,
        )
        self.db.add(correction)
        return correction
