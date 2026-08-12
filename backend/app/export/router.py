import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.export import service
from app.export.csv_exporter import export_csv
from app.export.excel_exporter import export_excel
from app.export.tally_xml_exporter import export_tally_xml
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.parsed_transaction_repository import ParsedTransactionRepository

router = APIRouter(prefix="/export", tags=["export"])

# Export content depends on live job/transaction state (per the "re-validated at
# export time, never trusts stale state" principle) and reuses the same URL for
# every download of a given job/format, so the browser must never silently reuse a
# cached response from before a fix or a later review correction.
_NO_STORE_HEADERS = {"Cache-Control": "no-store"}


def _prepare_export_rows(db: Session, job_id: uuid.UUID, user: User, force: bool):
    job = JobRepository(db).get_by_id_for_user(job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        service.check_job_exportable(job)
        transactions = ParsedTransactionRepository(db).list_for_job(job_id)
        service.check_export_readiness(transactions, force)
    except service.ExportNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ExportBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    rows = service.build_export_rows(db, transactions)
    service.mark_exported(db, job)
    return rows


@router.get("/{job_id}/csv")
def export_job_csv(
    job_id: uuid.UUID,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    rows = _prepare_export_rows(db, job_id, current_user, force)
    return Response(
        content=export_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="job-{job_id}.csv"',
            **_NO_STORE_HEADERS,
        },
    )


@router.get("/{job_id}/excel")
def export_job_excel(
    job_id: uuid.UUID,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    rows = _prepare_export_rows(db, job_id, current_user, force)
    return Response(
        content=export_excel(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="job-{job_id}.xlsx"',
            **_NO_STORE_HEADERS,
        },
    )


@router.get("/{job_id}/xml")
def export_job_xml(
    job_id: uuid.UUID,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    rows = _prepare_export_rows(db, job_id, current_user, force)
    return Response(
        content=export_tally_xml(rows),
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="job-{job_id}.xml"',
            **_NO_STORE_HEADERS,
        },
    )
