import io

import pytest

from app.config.settings import get_settings


@pytest.fixture(autouse=True)
def _use_tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "uploader@example.com", "password": "s3cret-pass", "full_name": "Uploader"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "uploader@example.com", "password": "s3cret-pass"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_csv_creates_queued_job(client, auth_headers):
    response = client.post(
        "/api/v1/upload",
        headers=auth_headers,
        files={"file": ("statement.csv", io.BytesIO(b"date,description,amount\n"), "text/csv")},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert job_response.status_code == 200
    body = job_response.json()
    assert body["status"] == "QUEUED"
    assert len(body["status_history"]) == 1

    list_response = client.get("/api/v1/jobs", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_upload_rejects_unsupported_file_type(client, auth_headers):
    response = client.post(
        "/api/v1/upload",
        headers=auth_headers,
        files={"file": ("statement.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 10)
    response = client.post(
        "/api/v1/upload",
        headers=auth_headers,
        files={"file": ("statement.csv", io.BytesIO(b"a" * 100), "text/csv")},
    )
    assert response.status_code == 413


def test_upload_requires_auth(client):
    response = client.post(
        "/api/v1/upload",
        files={"file": ("statement.csv", io.BytesIO(b"date,description,amount\n"), "text/csv")},
    )
    assert response.status_code == 401


def test_job_not_visible_to_other_user(client, auth_headers):
    upload_response = client.post(
        "/api/v1/upload",
        headers=auth_headers,
        files={"file": ("statement.csv", io.BytesIO(b"date,description,amount\n"), "text/csv")},
    )
    job_id = upload_response.json()["job_id"]

    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "s3cret-pass", "full_name": "Other"},
    )
    other_login = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "s3cret-pass"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get(f"/api/v1/jobs/{job_id}", headers=other_headers)
    assert response.status_code == 404
