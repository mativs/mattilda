from tests.helpers.auth import auth_header, school_header, token_for_user
from tests.helpers.rls import prepare_rls_tester, read_dummy_records_for_school


def test_user_school_student_end2end_flow_and_rls(client, db_session, seeded_users):
    """
    Validate a global multi-endpoint user journey with RLS verification.

    1. Authenticate as admin and create user, school, and student entities via API.
    2. Associate created user and student through school and student association endpoints.
    3. Validate created user can fetch self profile via token authentication.
    4. Validate RLS helper returns tenant-scoped records for each school context.
    """
    north_school_id = seeded_users["north_school"].id
    south_school_id = seeded_users["south_school"].id
    admin_token = token_for_user(seeded_users["admin"].id)

    created_user = client.post(
        "/api/v1/users",
        headers=school_header(admin_token, north_school_id),
        json={
            "email": "flow-user@example.com",
            "password": "flow12345",
            "is_active": True,
            "profile": {"first_name": "Flow", "last_name": "User"},
        },
    )
    assert created_user.status_code == 201
    created_user_id = created_user.json()["id"]

    created_school = client.post(
        "/api/v1/schools",
        headers=school_header(admin_token, north_school_id),
        json={"name": "Flow School", "slug": "flow-school"},
    )
    assert created_school.status_code == 201
    created_school_id = created_school.json()["id"]

    created_student = client.post(
        "/api/v1/students",
        headers=school_header(admin_token, created_school_id),
        json={"first_name": "Flow", "last_name": "Student", "external_id": "FLOW-001"},
    )
    assert created_student.status_code == 201
    created_student_id = created_student.json()["id"]

    school_link = client.post(
        f"/api/v1/schools/{created_school_id}/users",
        headers=school_header(admin_token, created_school_id),
        json={"user_id": created_user_id, "role": "teacher"},
    )
    assert school_link.status_code == 201

    user_student_link = client.post(
        f"/api/v1/students/{created_student_id}/users",
        headers=school_header(admin_token, created_school_id),
        json={"user_id": created_user_id},
    )
    assert user_student_link.status_code == 201

    me = client.get("/api/v1/users/me", headers=auth_header(token_for_user(created_user_id)))
    assert me.status_code == 200
    assert me.json()["email"] == "flow-user@example.com"

    prepare_rls_tester(db_session)
    assert read_dummy_records_for_school(db_session, north_school_id) == ["north-record"]
    assert read_dummy_records_for_school(db_session, south_school_id) == ["south-record"]
