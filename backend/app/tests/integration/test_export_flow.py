import uuid
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

import pytest

from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ParsedTransaction
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.uploaded_file import FileType, UploadedFile
from app.repositories.user_repository import UserRepository
from app.vouchers.voucher_generator import VoucherGenerator


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "exporter@example.com", "password": "s3cret-pass", "full_name": "Exporter"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "exporter@example.com", "password": "s3cret-pass"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_ledger(db_session, group_name="Sundry Creditors", ledger_name="VCT PRODUCTS"):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db_session.add(group)
    db_session.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db_session.add(ledger)
    db_session.commit()
    return group, ledger


def _seed_job(db_session, status, email="exporter@example.com"):
    user = UserRepository(db_session).get_by_email(email)
    uploaded_file = UploadedFile(
        user_id=user.id,
        original_filename="statement.csv",
        storage_path="/tmp/irrelevant.csv",
        file_type=FileType.CSV,
        file_size_bytes=10,
        checksum_sha256="irrelevant",
    )
    db_session.add(uploaded_file)
    db_session.flush()

    job = ProcessingJob(
        uploaded_file_id=uploaded_file.id,
        status=status,
        status_history=[{"status": status.value, "timestamp": "2026-08-12T00:00:00+00:00"}],
    )
    db_session.add(job)
    db_session.commit()
    return job


def _add_resolved_txn(db_session, job, ledger, row_number=1, debit="1000", credit="0"):
    txn = ParsedTransaction(
        processing_job_id=job.id,
        row_number=row_number,
        txn_date=date(2026, 1, row_number),
        original_narration="test narration",
        normalized_narration="TEST NARRATION",
        debit=Decimal(debit),
        credit=Decimal(credit),
        ledger_id=ledger.id,
        group_id=ledger.group_id,
    )
    db_session.add(txn)
    db_session.commit()
    VoucherGenerator(db_session).generate_for_transaction(txn)
    db_session.commit()
    return txn


def test_export_requires_auth(client):
    response = client.get(f"/api/v1/export/{uuid.uuid4()}/csv")
    assert response.status_code == 401


def test_export_404_for_other_users_job(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.READY)

    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "s3cret-pass", "full_name": "Other"},
    )
    other_login = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "s3cret-pass"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get(f"/api/v1/export/{job.id}/csv", headers=other_headers)
    assert response.status_code == 404


def test_export_409_while_job_still_processing(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.MATCHING)
    response = client.get(f"/api/v1/export/{job.id}/csv", headers=auth_headers)
    assert response.status_code == 409


def test_export_409_when_transactions_still_need_review(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.REVIEW_REQUIRED)
    _, ledger = _seed_ledger(db_session)
    txn = _add_resolved_txn(db_session, job, ledger)
    txn.requires_review = True
    db_session.commit()

    response = client.get(f"/api/v1/export/{job.id}/csv", headers=auth_headers)
    assert response.status_code == 409

    forced = client.get(f"/api/v1/export/{job.id}/csv", headers=auth_headers, params={"force": True})
    assert forced.status_code == 200


def test_export_csv_success_marks_job_exported(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.READY)
    _, ledger = _seed_ledger(db_session)
    _add_resolved_txn(db_session, job, ledger)

    response = client.get(f"/api/v1/export/{job.id}/csv", headers=auth_headers)
    assert response.status_code == 200
    assert "V00001" in response.text
    assert response.headers["content-type"].startswith("text/csv")
    # Export content depends on live job state and reuses the same URL every
    # download - the browser must never silently serve a stale cached copy.
    assert response.headers["cache-control"] == "no-store"

    job_response = client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers)
    assert job_response.json()["status"] == "EXPORTED"

    # re-export after EXPORTED should still work (idempotent, not a re-block)
    again = client.get(f"/api/v1/export/{job.id}/csv", headers=auth_headers)
    assert again.status_code == 200


def test_export_excel_success(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.READY)
    _, ledger = _seed_ledger(db_session)
    _add_resolved_txn(db_session, job, ledger)

    response = client.get(f"/api/v1/export/{job.id}/excel", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 0


def test_export_xml_success_and_well_formed(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.READY)
    _, ledger = _seed_ledger(db_session)
    _add_resolved_txn(db_session, job, ledger)

    response = client.get(f"/api/v1/export/{job.id}/xml", headers=auth_headers)
    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    assert root.find(".//VOUCHER") is not None


def test_export_excludes_duplicate_transactions(client, db_session, auth_headers):
    job = _seed_job(db_session, JobStatus.READY)
    _, ledger = _seed_ledger(db_session)
    kept = _add_resolved_txn(db_session, job, ledger, row_number=1)
    dup = _add_resolved_txn(db_session, job, ledger, row_number=2)
    dup.is_duplicate = True
    db_session.commit()

    response = client.get(f"/api/v1/export/{job.id}/csv", headers=auth_headers)
    assert response.status_code == 200
    body = response.text
    assert body.count("V0000") == 1  # only the kept row's voucher appears
