from sqlalchemy import text

from tests.helpers.auth import auth_header, login, school_header


def test_user_school_student_end2end_flow_and_rls(client, db_session, seeded_users):
    """
    Validate a global multi-endpoint user journey with RLS verification.

    1. Authenticate as admin and create a user, school, and student.
    2. Associate the created user and student across school and user-student links.
    3. Validate the created user can authenticate and read own profile context.
    4. Validate PostgreSQL RLS filters dummy records by active school context.
    """
    north_school_id = seeded_users["north_school"].id
    south_school_id = seeded_users["south_school"].id

    admin_token = login(client, "admin@example.com", "admin123")

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

    flow_token = login(client, "flow-user@example.com", "flow12345")
    me = client.get("/api/v1/users/me", headers=auth_header(flow_token))
    assert me.status_code == 200
    assert me.json()["email"] == "flow-user@example.com"

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
