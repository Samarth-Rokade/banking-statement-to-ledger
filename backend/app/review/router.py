import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.parsed_transaction import ResolutionSource
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.parsed_transaction_repository import ParsedTransactionRepository
from app.review import service
from app.schemas.transaction import (
    MarkDuplicateRequest,
    ParsedTransactionListResponse,
    ParsedTransactionOut,
    TransactionPatchRequest,
)

router = APIRouter(tags=["review"])


def _get_owned_transaction(db: Session, transaction_id: uuid.UUID, user: User):
    txn = ParsedTransactionRepository(db).get_by_id_for_user(transaction_id, user.id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.get("/jobs/{job_id}/transactions", response_model=ParsedTransactionListResponse)
def list_job_transactions(
    job_id: uuid.UUID,
    requires_review: bool | None = None,
    resolution_source: ResolutionSource | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedTransactionListResponse:
    job = JobRepository(db).get_by_id_for_user(job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    items, total = ParsedTransactionRepository(db).list_for_job_paginated(
        job_id, requires_review, resolution_source, page, page_size
    )
    return ParsedTransactionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/transactions/{transaction_id}", response_model=ParsedTransactionOut)
def get_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedTransactionOut:
    return _get_owned_transaction(db, transaction_id, current_user)


@router.post("/transactions/{transaction_id}/approve", response_model=ParsedTransactionOut)
def approve_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedTransactionOut:
    txn = _get_owned_transaction(db, transaction_id, current_user)
    try:
        service.approve_transaction(db, txn, current_user.id)
    except service.ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return txn


@router.patch("/transactions/{transaction_id}", response_model=ParsedTransactionOut)
def patch_transaction(
    transaction_id: uuid.UUID,
    body: TransactionPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedTransactionOut:
    txn = _get_owned_transaction(db, transaction_id, current_user)
    try:
        service.patch_transaction(db, txn, body.ledger_id, current_user.id)
    except service.ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return txn


@router.post("/transactions/{transaction_id}/mark-duplicate", response_model=ParsedTransactionOut)
def mark_duplicate(
    transaction_id: uuid.UUID,
    body: MarkDuplicateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedTransactionOut:
    txn = _get_owned_transaction(db, transaction_id, current_user)
    service.mark_duplicate(
        db, txn, body.is_duplicate, body.duplicate_of_transaction_id, current_user.id
    )
    return txn
