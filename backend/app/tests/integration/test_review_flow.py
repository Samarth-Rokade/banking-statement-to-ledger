import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.matcher.alias_matcher import AliasMatcher
from app.models.ledger import Ledger, LedgerCreatedVia
from app.models.ledger_alias import LedgerAliasSource
from app.models.ledger_group import LedgerGroup
from app.models.parsed_transaction import ParsedTransaction, ResolutionSource
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.uploaded_file import FileType, UploadedFile
from app.repositories.ledger_alias_repository import LedgerAliasRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "reviewer@example.com", "password": "s3cret-pass", "full_name": "Reviewer"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "reviewer@example.com", "password": "s3cret-pass"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_job_with_transactions(db_session, email="reviewer@example.com", status=JobStatus.REVIEW_REQUIRED):
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
        status_history=[{"status": status.value, "timestamp": "2026-08-09T00:00:00+00:00"}],
        total_transactions=2,
    )
    db_session.add(job)
    db_session.flush()

    resolved_txn = ParsedTransaction(
        processing_job_id=job.id,
        row_number=1,
        txn_date=date(2026, 1, 1),
        original_narration="AI predicted narration",
        normalized_narration="AI PREDICTED NARRATION",
        debit=Decimal("500"),
        credit=Decimal("0"),
        confidence=70,
        resolution_source=ResolutionSource.AI_PREDICTION,
        requires_review=True,
    )
    unresolved_txn = ParsedTransaction(
        processing_job_id=job.id,
        row_number=2,
        txn_date=date(2026, 1, 2),
        original_narration="Nobody could figure this one out",
        normalized_narration="NOBODY COULD FIGURE THIS ONE OUT",
        debit=Decimal("0"),
        credit=Decimal("1000"),
        requires_review=True,
    )
    db_session.add_all([resolved_txn, unresolved_txn])
    db_session.commit()
    return job, resolved_txn, unresolved_txn


def _seed_ledger(db_session, group_name="Sundry Creditors", ledger_name="VCT PRODUCTS"):
    group = LedgerGroup(name=group_name, tally_group_type=group_name)
    db_session.add(group)
    db_session.flush()
    ledger = Ledger(name=ledger_name, group_id=group.id, created_via=LedgerCreatedVia.MANUAL)
    db_session.add(ledger)
    db_session.commit()
    return group, ledger


def test_list_job_transactions_requires_auth(client, db_session):
    response = client.get(f"/api/v1/jobs/{uuid.uuid4()}/transactions")
    assert response.status_code == 401


def test_list_job_transactions_filters_by_requires_review(client, db_session, auth_headers):
    job, resolved_txn, unresolved_txn = _seed_job_with_transactions(db_session)

    response = client.get(f"/api/v1/jobs/{job.id}/transactions", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2

    filtered = client.get(
        f"/api/v1/jobs/{job.id}/transactions",
        headers=auth_headers,
        params={"resolution_source": "AI_PREDICTION"},
    )
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == str(resolved_txn.id)


def test_get_transaction_not_visible_to_other_user(client, db_session, auth_headers):
    _, _, unresolved_txn = _seed_job_with_transactions(db_session)

    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "s3cret-pass", "full_name": "Other"},
    )
    other_login = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "s3cret-pass"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get(f"/api/v1/transactions/{unresolved_txn.id}", headers=other_headers)
    assert response.status_code == 404


def test_approve_requires_ledger_already_assigned(client, db_session, auth_headers):
    _, _, unresolved_txn = _seed_job_with_transactions(db_session)

    response = client.post(
        f"/api/v1/transactions/{unresolved_txn.id}/approve", headers=auth_headers
    )
    assert response.status_code == 400


def test_approve_marks_reviewed_and_advances_job_when_last_row(client, db_session, auth_headers):
    job, resolved_txn, unresolved_txn = _seed_job_with_transactions(db_session)
    _, ledger = _seed_ledger(db_session)
    resolved_txn.ledger_id = ledger.id
    resolved_txn.group_id = ledger.group_id
    db_session.commit()

    response = client.post(
        f"/api/v1/transactions/{resolved_txn.id}/approve", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_review"] is False
    assert body["confidence"] == 100
    assert body["resolution_source"] == "MANUAL"
    assert body["reviewed_by_user_id"] is not None

    job_response = client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers)
    assert job_response.json()["manual_review_count"] == 1  # unresolved_txn still pending
    assert job_response.json()["status"] == "REVIEW_REQUIRED"


def test_patch_assigns_ledger_and_derives_group(client, db_session, auth_headers):
    job, resolved_txn, unresolved_txn = _seed_job_with_transactions(db_session)
    _, ledger = _seed_ledger(db_session)

    response = client.patch(
        f"/api/v1/transactions/{unresolved_txn.id}",
        headers=auth_headers,
        json={"ledger_id": str(ledger.id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ledger_id"] == str(ledger.id)
    assert body["group_id"] == str(ledger.group_id)
    assert body["resolution_source"] == "MANUAL"
    assert body["requires_review"] is False


def test_patch_rejects_nonexistent_ledger(client, db_session, auth_headers):
    _, _, unresolved_txn = _seed_job_with_transactions(db_session)

    response = client.patch(
        f"/api/v1/transactions/{unresolved_txn.id}",
        headers=auth_headers,
        json={"ledger_id": str(uuid.uuid4())},
    )
    assert response.status_code == 400


def test_job_advances_to_ready_once_every_row_is_resolved(client, db_session, auth_headers):
    job, resolved_txn, unresolved_txn = _seed_job_with_transactions(db_session)
    _, ledger = _seed_ledger(db_session)

    for txn in (resolved_txn, unresolved_txn):
        response = client.patch(
            f"/api/v1/transactions/{txn.id}",
            headers=auth_headers,
            json={"ledger_id": str(ledger.id)},
        )
        assert response.status_code == 200

    job_response = client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers)
    body = job_response.json()
    assert body["status"] == "READY"
    assert body["manual_review_count"] == 0
    assert body["export_ready_count"] == 2


def test_patch_learns_alias_that_resolves_the_next_matching_transaction(client, db_session, auth_headers):
    _, _, unresolved_txn = _seed_job_with_transactions(db_session)
    _, ledger = _seed_ledger(db_session)

    response = client.patch(
        f"/api/v1/transactions/{unresolved_txn.id}",
        headers=auth_headers,
        json={"ledger_id": str(ledger.id)},
    )
    assert response.status_code == 200

    alias = LedgerAliasRepository(db_session).get_by_alias(unresolved_txn.normalized_narration)
    assert alias is not None
    assert alias.ledger_id == ledger.id
    assert alias.source == LedgerAliasSource.LEARNED

    # A brand new transaction with the exact same normalized narration should now
    # resolve deterministically via Module 8 (Alias Match) - no AI needed.
    next_txn = ParsedTransaction(
        processing_job_id=unresolved_txn.processing_job_id,
        row_number=99,
        txn_date=date(2026, 2, 1),
        original_narration="same vendor, next month",
        normalized_narration=unresolved_txn.normalized_narration,
        debit=Decimal("0"),
        credit=Decimal("1000"),
    )
    db_session.add(next_txn)
    db_session.commit()

    resolved = AliasMatcher(db_session).try_resolve(next_txn)
    assert resolved is True
    assert next_txn.ledger_id == ledger.id
    assert next_txn.resolution_source == ResolutionSource.ALIAS_MATCH


def test_approve_learns_alias_from_ai_prediction(client, db_session, auth_headers):
    job, resolved_txn, _ = _seed_job_with_transactions(db_session)
    _, ledger = _seed_ledger(db_session, ledger_name="AI GUESSED VENDOR")
    resolved_txn.ledger_id = ledger.id
    resolved_txn.group_id = ledger.group_id
    db_session.commit()

    response = client.post(
        f"/api/v1/transactions/{resolved_txn.id}/approve", headers=auth_headers
    )
    assert response.status_code == 200

    alias = LedgerAliasRepository(db_session).get_by_alias(resolved_txn.normalized_narration)
    assert alias is not None
    assert alias.ledger_id == ledger.id
    assert alias.source == LedgerAliasSource.LEARNED


def test_mark_duplicate_flags_transaction_and_clears_review(client, db_session, auth_headers):
    job, resolved_txn, unresolved_txn = _seed_job_with_transactions(db_session)

    response = client.post(
        f"/api/v1/transactions/{unresolved_txn.id}/mark-duplicate",
        headers=auth_headers,
        json={"is_duplicate": True, "duplicate_of_transaction_id": str(resolved_txn.id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_duplicate"] is True
    assert body["duplicate_of_transaction_id"] == str(resolved_txn.id)
    assert body["requires_review"] is False
