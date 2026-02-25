from app.application.services.security_service import create_access_token

from tests.helpers.auth import auth_header


def test_issue_token_success_and_invalid_credentials(client, db_session, seeded_users):
    """
    Validate auth token endpoint contract for success and failures.

    1. Request token with valid seeded credentials.
    2. Validate access token is present in successful response.
    3. Request token with wrong password and unknown user.
    4. Validate invalid credential attempts return unauthorized status.
    """
    ok = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@example.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    wrong_password = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert wrong_password.status_code == 401

    unknown = client.post(
        "/api/v1/auth/token",
        data={"username": "unknown@example.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert unknown.status_code == 401

    invalid_token = client.get("/api/v1/users/me", headers=auth_header("invalid-token"))
    assert invalid_token.status_code == 401

    inactive_token = create_access_token(seeded_users["student"].id)
    seeded_users["student"].is_active = False
    db_session.commit()
    inactive_user = client.get("/api/v1/users/me", headers=auth_header(inactive_token))
    assert inactive_user.status_code == 401
