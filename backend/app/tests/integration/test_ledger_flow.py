import pytest

from app.models.ledger_group import LedgerGroup


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "ledgermaster@example.com", "password": "s3cret-pass", "full_name": "LM"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "ledgermaster@example.com", "password": "s3cret-pass"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_ledger_requires_auth(client):
    response = client.post("/api/v1/ledgers", json={"name": "X", "group_id": "00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 401


def test_create_ledger_success(client, db_session, auth_headers):
    group = LedgerGroup(name="Sundry Creditors", tally_group_type="Sundry Creditors")
    db_session.add(group)
    db_session.commit()

    response = client.post(
        "/api/v1/ledgers",
        headers=auth_headers,
        json={"name": "New Vendor Ltd", "group_id": str(group.id)},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "New Vendor Ltd"
    assert body["group_id"] == str(group.id)
    assert body["created_via"] == "MANUAL"

    listed = client.get("/api/v1/ledgers", headers=auth_headers, params={"q": "New Vendor"})
    assert listed.status_code == 200
    assert any(l["name"] == "New Vendor Ltd" for l in listed.json())


def test_create_ledger_rejects_duplicate_name(client, db_session, auth_headers):
    group = LedgerGroup(name="Sundry Creditors", tally_group_type="Sundry Creditors")
    db_session.add(group)
    db_session.commit()

    client.post(
        "/api/v1/ledgers", headers=auth_headers, json={"name": "Dup Ltd", "group_id": str(group.id)}
    )
    response = client.post(
        "/api/v1/ledgers", headers=auth_headers, json={"name": "Dup Ltd", "group_id": str(group.id)}
    )
    assert response.status_code == 400


def test_create_ledger_rejects_missing_group(client, db_session, auth_headers):
    response = client.post(
        "/api/v1/ledgers",
        headers=auth_headers,
        json={"name": "Orphan Ltd", "group_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 400
