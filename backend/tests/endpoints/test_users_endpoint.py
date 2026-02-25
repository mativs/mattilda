from tests.helpers.auth import auth_header, login, school_header


def test_users_endpoints_authz_and_crud_contract(client, seeded_users):
    """
    Validate users endpoint authorization and CRUD response behavior.

    1. Validate unauthenticated access is denied and admin can create/list users.
    2. Validate non-admin cannot list users but can access own user resource.
    3. Validate admin update and soft-delete behavior for a created user.
    4. Validate expected 404 and 409 branches for missing and duplicate users.
    """
    north_school_id = seeded_users["north_school"].id
    student_id = seeded_users["student"].id

    unauthenticated = client.get("/api/v1/users")
    assert unauthenticated.status_code == 401

    admin_token = login(client, "admin@example.com", "admin123")
    created = client.post(
        "/api/v1/users",
        headers=school_header(admin_token, north_school_id),
        json={
            "email": "endpoint-user@example.com",
            "password": "abc12345",
            "is_active": True,
            "profile": {"first_name": "Endpoint", "last_name": "User"},
        },
    )
    assert created.status_code == 201
    created_id = created.json()["id"]

    duplicate = client.post(
        "/api/v1/users",
        headers=school_header(admin_token, north_school_id),
        json={
            "email": "endpoint-user@example.com",
            "password": "abc12345",
            "is_active": True,
            "profile": {"first_name": "Endpoint", "last_name": "User"},
        },
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/users", headers=school_header(admin_token, north_school_id))
    assert listed.status_code == 200
    assert all(user["id"] != created_id for user in listed.json())

    student_token = login(client, "student@example.com", "student123")
    student_list = client.get("/api/v1/users", headers=school_header(student_token, north_school_id))
    assert student_list.status_code == 403

    self_user = client.get(f"/api/v1/users/{student_id}", headers=school_header(student_token, north_school_id))
    assert self_user.status_code == 200
    other_user = client.get(f"/api/v1/users/{created_id}", headers=school_header(student_token, north_school_id))
    assert other_user.status_code == 403

    updated = client.put(
        f"/api/v1/users/{created_id}",
        headers=school_header(admin_token, north_school_id),
        json={"email": "endpoint-user2@example.com", "profile": {"first_name": "Edited"}},
    )
    assert updated.status_code == 200
    assert updated.json()["email"] == "endpoint-user2@example.com"

    update_missing = client.put(
        "/api/v1/users/9999",
        headers=school_header(admin_token, north_school_id),
        json={"email": "missing@example.com"},
    )
    assert update_missing.status_code == 404

    delete_missing = client.delete("/api/v1/users/9999", headers=school_header(admin_token, north_school_id))
    assert delete_missing.status_code == 404

    delete_ok = client.delete(f"/api/v1/users/{created_id}", headers=school_header(admin_token, north_school_id))
    assert delete_ok.status_code == 204
    get_deleted = client.get(f"/api/v1/users/{created_id}", headers=school_header(admin_token, north_school_id))
    assert get_deleted.status_code == 404

    me = client.get("/api/v1/users/me", headers=auth_header(admin_token))
    assert me.status_code == 200
