from tests.helpers.auth import login, school_header


def test_students_endpoints_role_aware_list_and_crud_contract(client, seeded_users):
    """
    Validate students endpoint role-aware listing and CRUD contracts.

    1. Validate admin and non-admin list behavior in active school.
    2. Validate create auto-association and duplicate external id conflict.
    3. Validate association/deassociation endpoints and error branches.
    4. Validate update, delete, and forbidden access contracts.
    """
    north_school_id = seeded_users["north_school"].id
    south_school_id = seeded_users["south_school"].id

    admin_token = login(client, "admin@example.com", "admin123")
    student_token = login(client, "student@example.com", "student123")

    admin_list = client.get("/api/v1/students", headers=school_header(admin_token, north_school_id))
    assert admin_list.status_code == 200
    assert len(admin_list.json()) >= 2

    student_list = client.get("/api/v1/students", headers=school_header(student_token, north_school_id))
    assert student_list.status_code == 200
    student_ids = {student["id"] for student in student_list.json()}
    assert seeded_users["child_one"].id in student_ids
    student_forbidden_school = client.get("/api/v1/students", headers=school_header(student_token, south_school_id))
    assert student_forbidden_school.status_code == 403

    created = client.post(
        "/api/v1/students",
        headers=school_header(admin_token, north_school_id),
        json={"first_name": "End", "last_name": "Point", "external_id": "EP-001"},
    )
    assert created.status_code == 201
    created_id = created.json()["id"]
    get_ok = client.get(f"/api/v1/students/{created_id}", headers=school_header(admin_token, north_school_id))
    assert get_ok.status_code == 200

    duplicate = client.post(
        "/api/v1/students",
        headers=school_header(admin_token, north_school_id),
        json={"first_name": "End", "last_name": "Dup", "external_id": "EP-001"},
    )
    assert duplicate.status_code == 409

    forbidden_create = client.post(
        "/api/v1/students",
        headers=school_header(student_token, north_school_id),
        json={"first_name": "No", "last_name": "Access"},
    )
    assert forbidden_create.status_code == 403

    duplicate_school_assoc = client.post(
        f"/api/v1/students/{created_id}/schools",
        headers=school_header(admin_token, north_school_id),
        json={"school_id": north_school_id},
    )
    assert duplicate_school_assoc.status_code == 409

    school_assoc = client.post(
        f"/api/v1/students/{created_id}/schools",
        headers=school_header(admin_token, north_school_id),
        json={"school_id": south_school_id},
    )
    assert school_assoc.status_code == 201

    user_assoc = client.post(
        f"/api/v1/students/{created_id}/users",
        headers=school_header(admin_token, north_school_id),
        json={"user_id": seeded_users["student"].id},
    )
    assert user_assoc.status_code == 201

    deassoc_user = client.delete(
        f"/api/v1/students/{created_id}/users/{seeded_users['student'].id}",
        headers=school_header(admin_token, north_school_id),
    )
    assert deassoc_user.status_code == 204

    deassoc_school = client.delete(
        f"/api/v1/students/{created_id}/schools/{south_school_id}",
        headers=school_header(admin_token, north_school_id),
    )
    assert deassoc_school.status_code == 204

    update_ok = client.put(
        f"/api/v1/students/{created_id}",
        headers=school_header(admin_token, north_school_id),
        json={"first_name": "Edited"},
    )
    assert update_ok.status_code == 200
    get_missing = client.get("/api/v1/students/9999", headers=school_header(admin_token, north_school_id))
    assert get_missing.status_code == 404
    update_missing = client.put(
        "/api/v1/students/9999",
        headers=school_header(admin_token, north_school_id),
        json={"first_name": "Missing"},
    )
    assert update_missing.status_code == 404
    delete_missing = client.delete("/api/v1/students/9999", headers=school_header(admin_token, north_school_id))
    assert delete_missing.status_code == 404

    delete_ok = client.delete(
        f"/api/v1/students/{created_id}",
        headers=school_header(admin_token, north_school_id),
    )
    assert delete_ok.status_code == 204
