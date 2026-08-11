from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.repositories.ledger_group_repository import LedgerGroupRepository
from app.repositories.ledger_repository import LedgerRepository
from app.schemas.ledger import LedgerGroupOut, LedgerOut

router = APIRouter(tags=["ledgers"])


@router.get("/ledgers", response_model=list[LedgerOut])
def list_ledgers(
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LedgerOut]:
    return LedgerRepository(db).list_all(search=q)


@router.get("/groups", response_model=list[LedgerGroupOut])
def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LedgerGroupOut]:
    return LedgerGroupRepository(db).list_all()
