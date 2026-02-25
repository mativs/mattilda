import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import text

from app.application.services.security_service import create_access_token, decode_access_token, hash_password, verify_password
from app.config import settings
from app.domain.roles import UserRole
from app.infrastructure.db.models import User
from app.interfaces.api.v1.dependencies.auth import get_current_school_id, require_school_roles, require_self_or_school_roles


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


def school_header(token: str, school_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-School-Id": str(school_id)}


def test_auth_and_users_end_to_end(client, db_session, seeded_users):
    """
    End-to-end authorization and user management flow.

    1. Validate unauthenticated and invalid login requests are rejected.
    2. Authenticate users and execute school-scoped create/list/read/update/delete user operations.
    3. Validate school visibility, tenant header checks, and membership-based role behavior.
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
    assert len(payload.json()["schools"]) == 2

    north_school_id = seeded_users["north_school"].id
    south_school_id = seeded_users["south_school"].id

    created = client.post(
        "/api/v1/users",
        headers=school_header(admin_token, north_school_id),
        json={
            "email": "newteacher@example.com",
            "password": "teacher123",
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
        headers=school_header(admin_token, north_school_id),
        json={
            "email": "newteacher@example.com",
            "password": "teacher123",
            "is_active": True,
            "profile": {"first_name": "Teacher", "last_name": "Dup"},
        },
    )
    assert duplicate_create.status_code == 409

    all_users = client.get("/api/v1/users", headers=school_header(admin_token, north_school_id))
    assert all_users.status_code == 200
    assert len(all_users.json()) == 3

    teacher_id = created_user["id"]
    get_teacher_admin = client.get(f"/api/v1/users/{teacher_id}", headers=school_header(admin_token, north_school_id))
    assert get_teacher_admin.status_code == 200

    missing_user = client.get("/api/v1/users/9999", headers=school_header(admin_token, north_school_id))
    assert missing_user.status_code == 404

    update_teacher = client.put(
        f"/api/v1/users/{teacher_id}",
        headers=school_header(admin_token, north_school_id),
        json={
            "email": "teacher2@example.com",
            "password": "teacher456",
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
    assert update_teacher.json()["is_active"] is False
    assert update_teacher.json()["profile"]["first_name"] == "Updated"
    assert update_teacher.json()["profile"]["phone"] == "555"

    duplicate_update = client.put(
        f"/api/v1/users/{teacher_id}",
        headers=school_header(admin_token, north_school_id),
        json={"email": "student@example.com"},
    )
    assert duplicate_update.status_code == 409

    update_missing = client.put(
        "/api/v1/users/9999",
        headers=school_header(admin_token, north_school_id),
        json={"email": "missing@example.com"},
    )
    assert update_missing.status_code == 404

    student_token = login(client, "student@example.com", "student123")
    users_forbidden = client.get("/api/v1/users", headers=school_header(student_token, north_school_id))
    assert users_forbidden.status_code == 403

    student_id = seeded_users["student"].id
    self_user = client.get(f"/api/v1/users/{student_id}", headers=school_header(student_token, north_school_id))
    assert self_user.status_code == 200

    other_user_forbidden = client.get(f"/api/v1/users/{teacher_id}", headers=school_header(student_token, north_school_id))
    assert other_user_forbidden.status_code == 403

    admin_schools = client.get("/api/v1/schools", headers=auth_header(admin_token))
    assert admin_schools.status_code == 200
    assert len(admin_schools.json()) == 2

    student_schools = client.get("/api/v1/schools", headers=auth_header(student_token))
    assert student_schools.status_code == 200
    assert len(student_schools.json()) == 1
    assert student_schools.json()[0]["slug"] == "north-high"

    student_get_school = client.get(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(student_token, north_school_id),
    )
    assert student_get_school.status_code == 200
    assert student_get_school.json()["slug"] == "north-high"

    admin_get_school = client.get(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(admin_token, north_school_id),
    )
    assert admin_get_school.status_code == 200
    mismatch_header_for_admin = client.get(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(admin_token, south_school_id),
    )
    assert mismatch_header_for_admin.status_code == 400

    missing_school_header = client.get(f"/api/v1/schools/{north_school_id}", headers=auth_header(student_token))
    assert missing_school_header.status_code == 400

    mismatched_school_header = client.get(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(student_token, south_school_id),
    )
    assert mismatched_school_header.status_code == 403

    admin_create_school = client.post(
        "/api/v1/schools",
        headers=auth_header(admin_token),
        json={
            "name": "West High",
            "slug": "west-high",
            "members": [
                {"user_id": seeded_users["teacher"].id, "roles": ["teacher"]},
                {"user_id": seeded_users["student"].id, "roles": ["student"]},
            ],
        },
    )
    assert admin_create_school.status_code == 201
    west_school_id = admin_create_school.json()["id"]

    admin_create_school_without_members = client.post(
        "/api/v1/schools",
        headers=auth_header(admin_token),
        json={"name": "East High", "slug": "east-high"},
    )
    assert admin_create_school_without_members.status_code == 201

    invalid_member_school = client.post(
        "/api/v1/schools",
        headers=auth_header(admin_token),
        json={
            "name": "Invalid Members",
            "slug": "invalid-members",
            "members": [{"user_id": 999999, "roles": ["teacher"]}],
        },
    )
    assert invalid_member_school.status_code == 404

    duplicate_school_slug = client.post(
        "/api/v1/schools",
        headers=auth_header(admin_token),
        json={"name": "West Copy", "slug": "west-high"},
    )
    assert duplicate_school_slug.status_code == 409

    student_create_school = client.post(
        "/api/v1/schools",
        headers=auth_header(student_token),
        json={"name": "Not Allowed", "slug": "not-allowed"},
    )
    assert student_create_school.status_code == 201

    update_school_resp = client.put(
        f"/api/v1/schools/{west_school_id}",
        headers=school_header(admin_token, west_school_id),
        json={
            "name": "West Academy",
            "slug": "west-academy",
            "is_active": False,
            "members": [
                {"user_id": seeded_users["admin"].id, "roles": ["director"]},
                {"user_id": seeded_users["teacher"].id, "roles": ["teacher"]},
            ],
        },
    )
    assert update_school_resp.status_code == 200
    assert update_school_resp.json()["name"] == "West Academy"
    assert update_school_resp.json()["slug"] == "west-academy"
    assert update_school_resp.json()["is_active"] is False

    duplicate_slug_update = client.put(
        f"/api/v1/schools/{west_school_id}",
        headers=school_header(admin_token, west_school_id),
        json={"slug": "north-high"},
    )
    assert duplicate_slug_update.status_code == 409

    mismatch_update_school = client.put(
        f"/api/v1/schools/{west_school_id}",
        headers=school_header(admin_token, north_school_id),
        json={"name": "Mismatch"},
    )
    assert mismatch_update_school.status_code == 400

    update_missing_school = client.put(
        "/api/v1/schools/9999",
        headers=school_header(admin_token, 9999),
        json={"name": "Missing School"},
    )
    assert update_missing_school.status_code == 404

    delete_school_resp = client.delete(f"/api/v1/schools/{west_school_id}", headers=school_header(admin_token, west_school_id))
    assert delete_school_resp.status_code == 204

    mismatch_delete_school = client.delete(f"/api/v1/schools/{north_school_id}", headers=school_header(admin_token, south_school_id))
    assert mismatch_delete_school.status_code == 400

    delete_missing_school = client.delete("/api/v1/schools/9999", headers=school_header(admin_token, 9999))
    assert delete_missing_school.status_code == 404

    delete_missing = client.delete("/api/v1/users/9999", headers=school_header(admin_token, north_school_id))
    assert delete_missing.status_code == 404

    delete_teacher = client.delete(f"/api/v1/users/{teacher_id}", headers=school_header(admin_token, north_school_id))
    assert delete_teacher.status_code == 204

    teacher_after_delete = client.get(f"/api/v1/users/{teacher_id}", headers=school_header(admin_token, north_school_id))
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

    db_session.execute(text("DROP ROLE IF EXISTS rls_tester"))
    db_session.execute(text("CREATE ROLE rls_tester LOGIN PASSWORD 'rls_tester'"))
    db_session.execute(text("GRANT USAGE ON SCHEMA public TO rls_tester"))
    db_session.execute(text("GRANT SELECT ON dummy_records TO rls_tester"))
    db_session.commit()

    connection = db_session.get_bind().connect()
    connection.execute(text("SET ROLE rls_tester"))
    connection.execute(text("SELECT set_config('app.current_school_id', :school_id, false)"), {"school_id": str(north_school_id)})
    rls_north_records = connection.execute(text("SELECT name FROM dummy_records ORDER BY name")).all()
    assert [record[0] for record in rls_north_records] == ["north-record"]

    connection.execute(text("SELECT set_config('app.current_school_id', :school_id, false)"), {"school_id": str(south_school_id)})
    rls_south_records = connection.execute(text("SELECT name FROM dummy_records ORDER BY name")).all()
    assert [record[0] for record in rls_south_records] == ["south-record"]
    connection.close()


def test_security_helpers_and_dependency_error_branch(client, seeded_users):
    """
    Unit-level validation for security helpers and auth dependency edge cases.

    1. Create and decode JWT tokens for valid and invalid payload cases.
    2. Validate password hashing and verification behavior and header parsing failures.
    3. Mock dependency calls to trigger path param, self-check, and school-role branches.
    4. Validate dependency success branches and school-not-found behavior via API.
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

    dependency = require_self_or_school_roles("missing", [UserRole.admin])

    class RequestStub:
        path_params: dict[str, str] = {}

    class CurrentUserStub:
        id = 1

    with pytest.raises(HTTPException) as exc:
        dependency(RequestStub(), CurrentUserStub(), [])
    assert exc.value.status_code == 400
    assert "Missing user id parameter" in str(exc.value.detail)

    with pytest.raises(HTTPException) as header_exc:
        get_current_school_id("abc")
    assert header_exc.value.status_code == 400

    school_dependency = require_school_roles([UserRole.teacher])

    class MembershipStub:
        role = UserRole.student.value

    with pytest.raises(HTTPException) as school_exc:
        school_dependency([MembershipStub()], CurrentUserStub())
    assert school_exc.value.status_code == 403
    assert "Insufficient school permissions" in str(school_exc.value.detail)

    class TeacherMembershipStub:
        role = UserRole.teacher.value

    assert school_dependency([TeacherMembershipStub()], CurrentUserStub()).id == 1

    class RequestSelfStub:
        path_params: dict[str, str] = {"target": "1"}

    assert require_self_or_school_roles("target", [UserRole.admin])(RequestSelfStub(), CurrentUserStub(), []).id == 1

    class RequestOtherStub:
        path_params: dict[str, str] = {"target": "2"}

    assert require_self_or_school_roles("target", [UserRole.teacher])(
        RequestOtherStub(),
        CurrentUserStub(),
        [TeacherMembershipStub()],
    ).id == 1

    admin_token = login(client, "admin@example.com", "admin123")
    school_not_found = client.get("/api/v1/schools/9999", headers={**auth_header(admin_token), "X-School-Id": "9999"})
    assert school_not_found.status_code == 404
