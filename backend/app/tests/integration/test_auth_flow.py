def test_register_login_me_flow(client):
    register_payload = {
        "email": "jane@example.com",
        "password": "s3cret-pass",
        "full_name": "Jane Doe",
    }
    register_response = client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["email"] == register_payload["email"]
    assert "hashed_password" not in body

    duplicate_response = client.post("/api/v1/auth/register", json=register_payload)
    assert duplicate_response.status_code == 409

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    wrong_password_response = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": "wrong-pass"},
    )
    assert wrong_password_response.status_code == 401

    me_response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == register_payload["email"]

    unauthenticated_response = client.get("/api/v1/auth/me")
    assert unauthenticated_response.status_code == 401
