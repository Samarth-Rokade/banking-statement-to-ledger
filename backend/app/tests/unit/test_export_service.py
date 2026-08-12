import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.export.service import (
    ExportBlockedError,
    ExportNotReadyError,
    build_export_rows,
    check_export_readiness,
    check_job_exportable,
    mark_exported,
)
from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ParsedTransaction
from app.models.processing_job import JobStatus, ProcessingJob
from app.vouchers.voucher_generator import VoucherGenerator


def _seed_group_and_ledger(db, group_name="Sundry Creditors", ledger_name="VCT PRODUCTS"):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db.add(group)
    db.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db.add(ledger)
    db.commit()
    return group, ledger


def _resolved_txn(db, ledger, job_id=None, row_number=1, debit="1000", credit="0"):
    txn = ParsedTransaction(
        processing_job_id=job_id or uuid.uuid4(),
        row_number=row_number,
        txn_date=date(2026, 1, row_number),
        original_narration="test narration",
        normalized_narration="TEST NARRATION",
        debit=Decimal(debit),
        credit=Decimal(credit),
        ledger_id=ledger.id,
        group_id=ledger.group_id,
    )
    db.add(txn)
    db.commit()
    VoucherGenerator(db).generate_for_transaction(txn)
    db.commit()
    return txn


def test_check_job_exportable_blocks_mid_pipeline_statuses(db_session):
    job = ProcessingJob(uploaded_file_id=uuid.uuid4(), status=JobStatus.MATCHING, status_history=[])
    with pytest.raises(ExportNotReadyError):
        check_job_exportable(job)


def test_check_job_exportable_blocks_failed(db_session):
    job = ProcessingJob(uploaded_file_id=uuid.uuid4(), status=JobStatus.FAILED, status_history=[])
    with pytest.raises(ExportNotReadyError):
        check_job_exportable(job)


def test_check_job_exportable_allows_ready_and_review_required_and_exported():
    for status in (JobStatus.READY, JobStatus.REVIEW_REQUIRED, JobStatus.EXPORTED):
        job = ProcessingJob(uploaded_file_id=uuid.uuid4(), status=status, status_history=[])
        check_job_exportable(job)  # should not raise


def test_check_export_readiness_blocks_on_unresolved_and_review(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    resolved = _resolved_txn(db_session, ledger, row_number=1)
    unresolved = ParsedTransaction(
        processing_job_id=resolved.processing_job_id,
        row_number=2,
        txn_date=date(2026, 1, 2),
        original_narration="unresolved",
        debit=Decimal("500"),
        credit=Decimal("0"),
    )
    db_session.add(unresolved)
    db_session.commit()

    with pytest.raises(ExportBlockedError):
        check_export_readiness([resolved, unresolved], force=False)

    check_export_readiness([resolved, unresolved], force=True)  # should not raise


def test_check_export_readiness_ignores_duplicates(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    resolved = _resolved_txn(db_session, ledger, row_number=1)
    duplicate = ParsedTransaction(
        processing_job_id=resolved.processing_job_id,
        row_number=2,
        txn_date=date(2026, 1, 2),
        original_narration="dup",
        debit=Decimal("500"),
        credit=Decimal("0"),
        is_duplicate=True,
    )
    db_session.add(duplicate)
    db_session.commit()

    check_export_readiness([resolved, duplicate], force=False)  # should not raise


def test_build_export_rows_excludes_unresolved_review_and_duplicate_rows(db_session):
    _, ledger = _seed_group_and_ledger(db_session)
    job_id = uuid.uuid4()
    resolved = _resolved_txn(db_session, ledger, job_id=job_id, row_number=1)

    unresolved = ParsedTransaction(
        processing_job_id=job_id, row_number=2, txn_date=date(2026, 1, 2),
        original_narration="unresolved", debit=Decimal("100"), credit=Decimal("0"),
    )
    needs_review = ParsedTransaction(
        processing_job_id=job_id, row_number=3, txn_date=date(2026, 1, 3),
        original_narration="needs review", debit=Decimal("100"), credit=Decimal("0"),
        ledger_id=ledger.id, group_id=ledger.group_id, requires_review=True,
    )
    duplicate = ParsedTransaction(
        processing_job_id=job_id, row_number=4, txn_date=date(2026, 1, 4),
        original_narration="dup", debit=Decimal("100"), credit=Decimal("0"),
        ledger_id=ledger.id, group_id=ledger.group_id, is_duplicate=True,
    )
    db_session.add_all([unresolved, needs_review, duplicate])
    db_session.commit()

    rows = build_export_rows(
        db_session, [resolved, unresolved, needs_review, duplicate]
    )

    assert len(rows) == 1
    assert rows[0].ledger_name == "VCT PRODUCTS"
    assert rows[0].voucher_number == "V00001"
    assert rows[0].voucher_type == "Payment"


def test_mark_exported_sets_status_and_is_idempotent(db_session):
    job = ProcessingJob(
        uploaded_file_id=uuid.uuid4(), status=JobStatus.READY, status_history=[]
    )
    db_session.add(job)
    db_session.commit()

    mark_exported(db_session, job)
    assert job.status == JobStatus.EXPORTED
    assert job.status_history[-1]["status"] == "EXPORTED"

    mark_exported(db_session, job)  # re-export - should not duplicate history entries
    assert job.status_history[-1]["status"] == "EXPORTED"
    assert sum(1 for h in job.status_history if h["status"] == "EXPORTED") == 1
