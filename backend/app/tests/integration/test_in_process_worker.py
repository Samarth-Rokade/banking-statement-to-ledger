import io
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import get_settings
from app.database import Base, get_db
from app.main import app
from app.models.voucher_type import VoucherType


@pytest.fixture()
def isolated_engine():
    """A dedicated in-memory DB, separate from the shared `db_session` fixture's -
    both the test's HTTP requests and the background worker thread need to see the
    same data, but each needs its own Session object (Sessions aren't thread-safe to
    share), so both sides get sessions bound to this one engine instead.
    """
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    seed = session_factory()
    seed.add_all([VoucherType(name=name) for name in ["Receipt", "Payment", "Contra", "Journal"]])
    seed.commit()
    seed.close()
    yield session_factory
    Base.metadata.drop_all(engine)


@pytest.fixture()
def in_process_worker_client(isolated_engine, monkeypatch, tmp_path):
    """Spins up a real TestClient with the in-process worker actually enabled,
    pointed at the isolated DB above - proving the full upload -> wake -> worker
    thread -> job progresses pipeline works with zero manual run_once() calls.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "run_worker_in_process", True)
    monkeypatch.setattr(settings, "worker_poll_interval_seconds", 0.2)
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr("app.jobs.worker.SessionLocal", isolated_engine)

    def override_get_db():
        db = isolated_engine()
        try:
            yield db
        finally:
            db.close()

    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_upload_is_processed_by_in_process_worker_without_manual_run_once(in_process_worker_client):
    client = in_process_worker_client
    client.post(
        "/api/v1/auth/register",
        json={"email": "auto@example.com", "password": "s3cret-pass", "full_name": "Auto"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "auto@example.com", "password": "s3cret-pass"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n" "01-01-2026,UPI-SWIGGY,250.00,0,9750.00\n"
    ).encode()
    upload = client.post(
        "/api/v1/upload",
        headers=headers,
        files={"file": ("statement.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job_id"]

    deadline = time.monotonic() + 10
    status = "QUEUED"
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        status = response.json()["status"]
        if status != "QUEUED":
            break
        time.sleep(0.1)

    # No test code ever called run_once()/run_worker_loop directly - if this isn't
    # QUEUED anymore, the in-process worker picked it up and moved it on its own.
    assert status != "QUEUED"
