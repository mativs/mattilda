from tests.helpers.auth import auth_header, login, school_header


def test_schools_endpoints_membership_header_and_crud_contract(client, seeded_users):
    """
    Validate schools endpoint behavior for membership and CRUD operations.

    1. Validate school listing and school fetch header checks.
    2. Validate admin create school auto-membership semantics.
    3. Validate update/delete contracts and mismatch header branches.
    4. Validate user-school association and not-found branches.
    """
    north_school_id = seeded_users["north_school"].id
    south_school_id = seeded_users["south_school"].id

    admin_token = login(client, "admin@example.com", "admin123")
    student_token = login(client, "student@example.com", "student123")

    admin_schools = client.get("/api/v1/schools", headers=auth_header(admin_token))
    assert admin_schools.status_code == 200
    assert len(admin_schools.json()) >= 2

    student_schools = client.get("/api/v1/schools", headers=auth_header(student_token))
    assert student_schools.status_code == 200
    assert len(student_schools.json()) == 1

    missing_header = client.get(f"/api/v1/schools/{north_school_id}", headers=auth_header(admin_token))
    assert missing_header.status_code == 400
    get_ok = client.get(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(admin_token, north_school_id),
    )
    assert get_ok.status_code == 200
    mismatch_header = client.get(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(admin_token, south_school_id),
    )
    assert mismatch_header.status_code == 400

    created = client.post(
        "/api/v1/schools",
        headers=school_header(admin_token, north_school_id),
        json={"name": "Endpoint West", "slug": "endpoint-west"},
    )
    assert created.status_code == 201
    created_id = created.json()["id"]
    members = {member["user_id"]: member["roles"] for member in created.json()["members"]}
    assert seeded_users["admin"].id in members
    assert "admin" in members[seeded_users["admin"].id]

    duplicate_slug = client.post(
        "/api/v1/schools",
        headers=school_header(admin_token, north_school_id),
        json={"name": "Endpoint West 2", "slug": "endpoint-west"},
    )
    assert duplicate_slug.status_code == 409

    forbidden_create = client.post(
        "/api/v1/schools",
        headers=school_header(student_token, north_school_id),
        json={"name": "Nope", "slug": "nope"},
    )
    assert forbidden_create.status_code == 403

    update_ok = client.put(
        f"/api/v1/schools/{created_id}",
        headers=school_header(admin_token, created_id),
        json={"name": "Endpoint West Edited"},
    )
    assert update_ok.status_code == 200
    mismatch_update = client.put(
        f"/api/v1/schools/{created_id}",
        headers=school_header(admin_token, north_school_id),
        json={"name": "Mismatch"},
    )
    assert mismatch_update.status_code == 400

    update_missing = client.put(
        "/api/v1/schools/9999",
        headers=school_header(admin_token, 9999),
        json={"name": "Missing"},
    )
    assert update_missing.status_code == 404

    associate_user = client.post(
        f"/api/v1/schools/{north_school_id}/users",
        headers=school_header(admin_token, north_school_id),
        json={"user_id": seeded_users["teacher"].id, "role": "admin"},
    )
    assert associate_user.status_code == 201
    associate_missing_user = client.post(
        f"/api/v1/schools/{north_school_id}/users",
        headers=school_header(admin_token, north_school_id),
        json={"user_id": 999999, "role": "teacher"},
    )
    assert associate_missing_user.status_code == 404

    deassociate_user = client.delete(
        f"/api/v1/schools/{north_school_id}/users/{seeded_users['teacher'].id}",
        headers=school_header(admin_token, north_school_id),
    )
    assert deassociate_user.status_code == 204

    delete_ok = client.delete(f"/api/v1/schools/{created_id}", headers=school_header(admin_token, created_id))
    assert delete_ok.status_code == 204
    mismatch_delete = client.delete(
        f"/api/v1/schools/{north_school_id}",
        headers=school_header(admin_token, south_school_id),
    )
    assert mismatch_delete.status_code == 400
