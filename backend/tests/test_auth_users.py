import pytest
from fastapi import HTTPException
from jose import jwt

from app.application.services.security_service import create_access_token, decode_access_token, hash_password, verify_password
from app.config import settings
from app.domain.roles import UserRole
from app.infrastructure.db.models import User
from app.interfaces.api.v1.dependencies.auth import require_self_or_roles


def login(client, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_and_users_end_to_end(client, db_session, seeded_users):
    """
    End-to-end authorization and user management flow.

    1. Validate unauthenticated and invalid login requests are rejected.
    2. Authenticate as admin and execute create/list/read/update/delete user operations.
    3. Validate roles and ownership rules for a student user on protected endpoints.
    4. Validate inactive, invalid, and orphaned token scenarios are rejected as expected.
    """
    student_list_resp = client.get("/api/v1/users")
    assert student_list_resp.status_code == 401

    invalid_login = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert invalid_login.status_code == 401
    unknown_login = client.post(
        "/api/v1/auth/token",
        data={"username": "unknown@example.com", "password": "whatever"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert unknown_login.status_code == 401

    admin_token = login(client, "admin@example.com", "admin123")
    payload = client.get("/api/v1/users/me", headers=auth_header(admin_token))
    assert payload.status_code == 200
    assert "admin" in payload.json()["roles"]

    created = client.post(
        "/api/v1/users",
        headers=auth_header(admin_token),
        json={
            "email": "teacher@example.com",
            "password": "teacher123",
            "roles": ["teacher"],
            "is_active": True,
            "profile": {
                "first_name": "Teacher",
                "last_name": "One",
                "phone": "333",
                "address": "Teacher Street",
            },
        },
    )
    assert created.status_code == 201
    created_user = created.json()
    assert created_user["profile"]["first_name"] == "Teacher"

    duplicate_create = client.post(
        "/api/v1/users",
        headers=auth_header(admin_token),
        json={
            "email": "teacher@example.com",
            "password": "teacher123",
            "roles": ["teacher"],
            "is_active": True,
            "profile": {"first_name": "Teacher", "last_name": "Dup"},
        },
    )
    assert duplicate_create.status_code == 409

    all_users = client.get("/api/v1/users", headers=auth_header(admin_token))
    assert all_users.status_code == 200
    assert len(all_users.json()) == 3

    teacher_id = created_user["id"]
    get_teacher_admin = client.get(f"/api/v1/users/{teacher_id}", headers=auth_header(admin_token))
    assert get_teacher_admin.status_code == 200

    missing_user = client.get("/api/v1/users/9999", headers=auth_header(admin_token))
    assert missing_user.status_code == 404

    update_teacher = client.put(
        f"/api/v1/users/{teacher_id}",
        headers=auth_header(admin_token),
        json={
            "email": "teacher2@example.com",
            "password": "teacher456",
            "roles": ["director", "teacher"],
            "is_active": False,
            "profile": {
                "first_name": "Updated",
                "last_name": "Teacher",
                "phone": "555",
                "address": "Director Street",
            },
        },
    )
    assert update_teacher.status_code == 200
    assert "director" in update_teacher.json()["roles"]
    assert "teacher" in update_teacher.json()["roles"]
    assert update_teacher.json()["is_active"] is False
    assert update_teacher.json()["profile"]["first_name"] == "Updated"
    assert update_teacher.json()["profile"]["phone"] == "555"

    duplicate_update = client.put(
        f"/api/v1/users/{teacher_id}",
        headers=auth_header(admin_token),
        json={"email": "student@example.com"},
    )
    assert duplicate_update.status_code == 409

    update_missing = client.put(
        "/api/v1/users/9999",
        headers=auth_header(admin_token),
        json={"email": "missing@example.com"},
    )
    assert update_missing.status_code == 404

    student_token = login(client, "student@example.com", "student123")
    users_forbidden = client.get("/api/v1/users", headers=auth_header(student_token))
    assert users_forbidden.status_code == 403

    student_id = seeded_users["student"].id
    self_user = client.get(f"/api/v1/users/{student_id}", headers=auth_header(student_token))
    assert self_user.status_code == 200

    other_user_forbidden = client.get(f"/api/v1/users/{teacher_id}", headers=auth_header(student_token))
    assert other_user_forbidden.status_code == 403

    delete_missing = client.delete("/api/v1/users/9999", headers=auth_header(admin_token))
    assert delete_missing.status_code == 404

    delete_teacher = client.delete(f"/api/v1/users/{teacher_id}", headers=auth_header(admin_token))
    assert delete_teacher.status_code == 204

    teacher_after_delete = client.get(f"/api/v1/users/{teacher_id}", headers=auth_header(admin_token))
    assert teacher_after_delete.status_code == 404

    inactive_token = create_access_token(seeded_users["student"].id)
    db_user = db_session.get(User, seeded_users["student"].id)
    db_user.is_active = False
    db_session.commit()
    inactive_login = client.post(
        "/api/v1/auth/token",
        data={"username": "student@example.com", "password": "student123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert inactive_login.status_code == 401
    inactive_me = client.get("/api/v1/users/me", headers=auth_header(inactive_token))
    assert inactive_me.status_code == 401

    invalid_token_response = client.get("/api/v1/users/me", headers=auth_header("invalid-token"))
    assert invalid_token_response.status_code == 401
    nonexistent_token = create_access_token(987654)
    missing_user_response = client.get("/api/v1/users/me", headers=auth_header(nonexistent_token))
    assert missing_user_response.status_code == 401


def test_security_helpers_and_dependency_error_branch():
    """
    Unit-level validation for security helpers and auth dependency edge case.

    1. Create and decode JWT tokens for valid and invalid payload cases.
    2. Validate password hashing and verification behavior.
    3. Mock a dependency call without required path params.
    4. Validate that the dependency raises HTTP 400 as expected.
    """
    token = create_access_token(42, expires_minutes=1)
    assert decode_access_token(token) == 42
    assert decode_access_token("bad-token") is None

    wrong_sub = jwt.encode({"sub": "abc"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(wrong_sub) is None

    missing_sub = jwt.encode({"exp": 9999999999}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(missing_sub) is None

    hashed = hash_password("abc123")
    assert verify_password("abc123", hashed) is True
    assert verify_password("zzz", hashed) is False

    dependency = require_self_or_roles("missing", [UserRole.admin])

    class RequestStub:
        path_params: dict[str, str] = {}

    class CurrentUserStub:
        roles = [UserRole.student.value]
        id = 1

    with pytest.raises(HTTPException) as exc:
        dependency(RequestStub(), CurrentUserStub())
    assert exc.value.status_code == 400
    assert "Missing user id parameter" in str(exc.value.detail)
