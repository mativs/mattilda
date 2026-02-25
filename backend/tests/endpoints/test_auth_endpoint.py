from tests.helpers.auth import auth_header, token_for_user


def test_issue_token_returns_200_for_valid_credentials(client, seeded_users):
    """
    Validate token issuance with valid credentials.

    1. Call auth token endpoint with valid seeded credentials.
    2. Receive token response.
    3. Validate status code is successful.
    4. Validate access token key exists.
    """
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@example.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_issue_token_returns_401_for_wrong_password(client, seeded_users):
    """
    Validate token endpoint wrong-password branch.

    1. Call auth token endpoint with valid email and wrong password.
    2. Receive error response.
    3. Validate unauthorized status code.
    4. Validate endpoint rejects credentials.
    """
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


def test_issue_token_returns_401_for_unknown_email(client):
    """
    Validate token endpoint unknown-email branch.

    1. Call auth token endpoint with non-existing email.
    2. Receive error response.
    3. Validate unauthorized status code.
    4. Validate endpoint rejects unknown users.
    """
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "missing@example.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


def test_me_returns_401_for_invalid_token(client):
    """
    Validate protected me endpoint invalid-token branch.

    1. Call users me endpoint with malformed bearer token.
    2. Receive unauthorized response.
    3. Validate status code is unauthorized.
    4. Validate invalid token is rejected.
    """
    response = client.get("/api/v1/users/me", headers=auth_header("invalid-token"))
    assert response.status_code == 401


def test_me_returns_401_for_inactive_user_token(client, db_session, seeded_users):
    """
    Validate protected me endpoint inactive-user branch.

    1. Mark seeded user inactive and mint token for same user id.
    2. Call users me endpoint with that token.
    3. Receive unauthorized response.
    4. Validate inactive users cannot authenticate.
    """
    seeded_users["student"].is_active = False
    db_session.commit()
    response = client.get("/api/v1/users/me", headers=auth_header(token_for_user(seeded_users["student"].id)))
    assert response.status_code == 401
