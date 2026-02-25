from tests.helpers.auth import auth_header, school_header, token_for_user
from tests.helpers.factories import add_membership, create_school, create_user
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
    4. Validate payload uses paginated envelope.
    """
    response = client.get(
        "/api/v1/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["pagination"]["offset"] == 0
    assert payload["pagination"]["limit"] == 20


def test_get_users_applies_limit_and_offset(client, seeded_users, db_session):
    """
    Validate users list pagination slicing.

    1. Seed two extra school members in active school.
    2. Call users list endpoint with offset and limit once.
    3. Receive successful paginated response.
    4. Validate returned item count and pagination metadata.
    """
    first = create_user(db_session, "users-page-1@example.com")
    second = create_user(db_session, "users-page-2@example.com")
    add_membership(db_session, first.id, seeded_users["north_school"].id, UserRole.teacher)
    add_membership(db_session, second.id, seeded_users["north_school"].id, UserRole.teacher)
    response = client.get(
        "/api/v1/users?offset=1&limit=1",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["pagination"]["offset"] == 1
    assert payload["pagination"]["limit"] == 1
    assert payload["pagination"]["filtered_total"] >= 3


def test_get_users_applies_search_on_email_and_profile(client, seeded_users, db_session):
    """
    Validate users list search filtering behavior.

    1. Seed one matching and one non-matching school member.
    2. Call users list endpoint with search param once.
    3. Receive successful paginated response.
    4. Validate only matching user is returned.
    """
    matching = create_user(db_session, "needle-user@example.com")
    matching.profile.first_name = "Needle"
    matching.profile.last_name = "Person"
    non_matching = create_user(db_session, "other-user@example.com")
    add_membership(db_session, matching.id, seeded_users["north_school"].id, UserRole.teacher)
    add_membership(db_session, non_matching.id, seeded_users["north_school"].id, UserRole.teacher)
    db_session.commit()
    response = client.get(
        "/api/v1/users?search=needle",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    emails = {item["email"] for item in payload["items"]}
    assert "needle-user@example.com" in emails
    assert "other-user@example.com" not in emails
    assert payload["pagination"]["filtered_total"] <= payload["pagination"]["total"]


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


def test_update_user_applies_association_sync_payload(client, seeded_users, db_session):
    """
    Validate user update applies association add/remove payload.

    1. Seed target user with one school-role membership.
    2. Call update user endpoint with associations add/remove.
    3. Receive successful response payload.
    4. Validate memberships reflect requested delta.
    """
    target = create_user(db_session, "assoc-target@example.com")
    old_school = create_school(db_session, "Old Assoc School", "old-assoc-school")
    new_school = create_school(db_session, "New Assoc School", "new-assoc-school")
    add_membership(db_session, target.id, old_school.id, UserRole.teacher)
    add_membership(db_session, seeded_users["admin"].id, old_school.id, UserRole.admin)
    add_membership(db_session, seeded_users["admin"].id, new_school.id, UserRole.admin)
    response = client.put(
        f"/api/v1/users/{target.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "associations": {
                "add": {"school_roles": [{"school_id": new_school.id, "role": "admin"}]},
                "remove": {"school_roles": [{"school_id": old_school.id, "role": "teacher"}]},
            }
        },
    )
    assert response.status_code == 200
    memberships = {(school["school_id"], role) for school in response.json()["schools"] for role in school["roles"]}
    assert (old_school.id, "teacher") not in memberships
    assert (new_school.id, "admin") in memberships


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
