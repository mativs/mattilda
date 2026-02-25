from tests.helpers.auth import auth_header, school_header, token_for_user
from tests.helpers.factories import add_membership, create_user
from app.domain.roles import UserRole


def test_get_users_returns_401_without_token(client):
    """
    Validate users list unauthorized branch.

    1. Call users list endpoint without auth header.
    2. Receive error response.
    3. Validate unauthorized status code.
    4. Validate endpoint requires authentication.
    """
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_get_users_returns_200_for_school_admin(client, seeded_users):
    """
    Validate users list success for school admin.

    1. Build admin token and active school header.
    2. Call users list endpoint once.
    3. Receive successful response.
    4. Validate payload is a list.
    """
    response = client.get(
        "/api/v1/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_users_returns_403_for_non_admin(client, seeded_users):
    """
    Validate users list forbidden for non-admin member.

    1. Build student token and school header.
    2. Call users list endpoint once.
    3. Receive forbidden response.
    4. Validate non-admin cannot list users.
    """
    response = client.get(
        "/api/v1/users",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 403


def test_create_user_returns_201_for_school_admin(client, seeded_users):
    """
    Validate user creation success for school admin.

    1. Build admin school-scoped header.
    2. Call create user endpoint once.
    3. Receive successful creation response.
    4. Validate response contains created email.
    """
    response = client.post(
        "/api/v1/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "email": "endpoint-create@example.com",
            "password": "abc12345",
            "is_active": True,
            "profile": {"first_name": "Endpoint", "last_name": "Create"},
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == "endpoint-create@example.com"


def test_create_user_returns_409_for_duplicate_email(client, seeded_users, db_session):
    """
    Validate user creation duplicate-email branch.

    1. Seed user with target email.
    2. Call create user endpoint with same email.
    3. Receive conflict response.
    4. Validate duplicate create is rejected.
    """
    create_user(db_session, "existing@example.com")
    response = client.post(
        "/api/v1/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "email": "existing@example.com",
            "password": "abc12345",
            "is_active": True,
            "profile": {"first_name": "Dup", "last_name": "User"},
        },
    )
    assert response.status_code == 409


def test_get_me_returns_200_for_authenticated_user(client, seeded_users):
    """
    Validate users me endpoint success.

    1. Build token for seeded admin user.
    2. Call users me endpoint once.
    3. Receive successful response.
    4. Validate response id matches admin user.
    """
    response = client.get("/api/v1/users/me", headers=auth_header(token_for_user(seeded_users["admin"].id)))
    assert response.status_code == 200
    assert response.json()["id"] == seeded_users["admin"].id


def test_get_user_returns_200_for_self_access(client, seeded_users):
    """
    Validate users get-by-id self-access branch.

    1. Build student token and school header.
    2. Call own user id endpoint once.
    3. Receive successful response.
    4. Validate returned id matches student id.
    """
    response = client.get(
        f"/api/v1/users/{seeded_users['student'].id}",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == seeded_users["student"].id


def test_get_user_returns_403_for_other_user_without_admin_role(client, seeded_users):
    """
    Validate users get-by-id forbidden branch for non-admin.

    1. Build student token and school header.
    2. Call another user's endpoint once.
    3. Receive forbidden response.
    4. Validate ownership/role check is enforced.
    """
    response = client.get(
        f"/api/v1/users/{seeded_users['teacher'].id}",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 403


def test_get_user_returns_404_for_missing_user(client, seeded_users):
    """
    Validate users get-by-id missing user branch.

    1. Build admin token and school header.
    2. Call endpoint with non-existing user id.
    3. Receive not found response.
    4. Validate missing users return 404.
    """
    response = client.get(
        "/api/v1/users/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_update_user_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate user update success for admin.

    1. Seed target user and membership in active school.
    2. Call update user endpoint once.
    3. Receive successful response.
    4. Validate updated email value.
    """
    target = create_user(db_session, "update-target@example.com")
    add_membership(db_session, target.id, seeded_users["north_school"].id, UserRole.teacher)
    response = client.put(
        f"/api/v1/users/{target.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"email": "updated-target@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "updated-target@example.com"


def test_update_user_returns_404_for_missing_user(client, seeded_users):
    """
    Validate user update missing-user branch.

    1. Build admin token and school header.
    2. Call update endpoint with unknown user id.
    3. Receive not found response.
    4. Validate missing users return 404.
    """
    response = client.put(
        "/api/v1/users/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 404


def test_update_user_returns_409_for_duplicate_email(client, seeded_users, db_session):
    """
    Validate user update duplicate email conflict.

    1. Seed target user and existing user with conflicting email.
    2. Call update endpoint once.
    3. Receive conflict response.
    4. Validate duplicate email update is rejected.
    """
    target = create_user(db_session, "target-update@example.com")
    existing = create_user(db_session, "existing-update@example.com")
    add_membership(db_session, target.id, seeded_users["north_school"].id, UserRole.teacher)
    add_membership(db_session, existing.id, seeded_users["north_school"].id, UserRole.teacher)
    response = client.put(
        f"/api/v1/users/{target.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"email": "existing-update@example.com"},
    )
    assert response.status_code == 409


def test_delete_user_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate user delete success for admin.

    1. Seed target user with school membership.
    2. Call delete endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    target = create_user(db_session, "delete-target@example.com")
    add_membership(db_session, target.id, seeded_users["north_school"].id, UserRole.teacher)
    response = client.delete(
        f"/api/v1/users/{target.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_delete_user_returns_404_for_missing_user(client, seeded_users):
    """
    Validate user delete missing-user branch.

    1. Build admin token and school header.
    2. Call delete endpoint with unknown user id.
    3. Receive not found response.
    4. Validate missing users return 404.
    """
    response = client.delete(
        "/api/v1/users/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404
