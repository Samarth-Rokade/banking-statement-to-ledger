import uuid

from pydantic import BaseModel, ConfigDict


class LedgerGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    tally_group_type: str
    parent_group_id: uuid.UUID | None


class LedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    group_id: uuid.UUID
    usage_count: int
    confidence_baseline: int
    created_via: str


class LedgerCreate(BaseModel):
    name: str
    group_id: uuid.UUID
