from app.domain.roles import UserRole
from tests.helpers.auth import auth_header, school_header, token_for_user
from tests.helpers.factories import add_membership, create_school


def test_get_schools_returns_200_for_authenticated_user(client, seeded_users):
    """
    Validate schools list success for authenticated user.

    1. Build admin auth header.
    2. Call schools list endpoint once.
    3. Receive successful response.
    4. Validate payload uses paginated envelope.
    """
    response = client.get("/api/v1/schools", headers=auth_header(token_for_user(seeded_users["admin"].id)))
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["pagination"]["offset"] == 0
    assert payload["pagination"]["limit"] == 20


def test_get_schools_applies_limit_and_offset(client, seeded_users, db_session):
    """
    Validate schools list pagination slicing.

    1. Seed additional schools and memberships for current user.
    2. Call schools list endpoint with offset and limit once.
    3. Receive successful paginated response.
    4. Validate item count and pagination metadata.
    """
    school_one = create_school(db_session, "Offset One", "offset-one")
    school_two = create_school(db_session, "Offset Two", "offset-two")
    add_membership(db_session, seeded_users["admin"].id, school_one.id, UserRole.admin)
    add_membership(db_session, seeded_users["admin"].id, school_two.id, UserRole.admin)
    response = client.get(
        "/api/v1/schools?offset=1&limit=1", headers=auth_header(token_for_user(seeded_users["admin"].id))
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["pagination"]["offset"] == 1
    assert payload["pagination"]["limit"] == 1
    assert payload["pagination"]["filtered_total"] >= 3


def test_get_schools_applies_search_on_name_and_slug(client, seeded_users, db_session):
    """
    Validate schools list search filtering behavior.

    1. Seed one matching and one non-matching school for user.
    2. Call schools list endpoint with search param once.
    3. Receive successful paginated response.
    4. Validate only matching school is returned.
    """
    matching = create_school(db_session, "Needle Academy", "needle-academy")
    non_matching = create_school(db_session, "Other Campus", "other-campus")
    add_membership(db_session, seeded_users["admin"].id, matching.id, UserRole.admin)
    add_membership(db_session, seeded_users["admin"].id, non_matching.id, UserRole.admin)
    response = client.get(
        "/api/v1/schools?search=needle", headers=auth_header(token_for_user(seeded_users["admin"].id))
    )
    assert response.status_code == 200
    payload = response.json()
    slugs = {item["slug"] for item in payload["items"]}
    assert "needle-academy" in slugs
    assert "other-campus" not in slugs
    assert payload["pagination"]["filtered_total"] <= payload["pagination"]["total"]


def test_get_school_returns_400_when_header_is_missing(client, seeded_users):
    """
    Validate school get-by-id missing header branch.

    1. Build auth header without school selector.
    2. Call school get endpoint once.
    3. Receive bad request response.
    4. Validate X-School-Id is required.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=auth_header(token_for_user(seeded_users["admin"].id)),
    )
    assert response.status_code == 400


def test_get_school_returns_400_for_mismatched_path_and_header(client, seeded_users):
    """
    Validate school get-by-id header/path mismatch branch.

    1. Build admin header with different school id.
    2. Call school get endpoint once.
    3. Receive bad request response.
    4. Validate path school id must match header.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_get_school_returns_200_for_valid_header_and_membership(client, seeded_users):
    """
    Validate school get-by-id success branch.

    1. Build admin header for matching school id.
    2. Call school get endpoint once.
    3. Receive successful response.
    4. Validate returned school id.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == seeded_users["north_school"].id


def test_create_school_returns_201_for_school_admin(client, seeded_users):
    """
    Validate school creation success for school admin.

    1. Build admin school-scoped header.
    2. Call create school endpoint once.
    3. Receive created response.
    4. Validate creator appears with admin role.
    """
    response = client.post(
        "/api/v1/schools",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Endpoint School", "slug": "endpoint-school"},
    )
    assert response.status_code == 201
    roles_map = {member["user_id"]: member["roles"] for member in response.json()["members"]}
    assert "admin" in roles_map[seeded_users["admin"].id]


def test_create_school_returns_409_for_duplicate_slug(client, seeded_users, db_session):
    """
    Validate school creation duplicate slug conflict.

    1. Seed school with target slug.
    2. Call create school endpoint with duplicate slug.
    3. Receive conflict response.
    4. Validate duplicate slug is rejected.
    """
    create_school(db_session, "Existing", "dup-school")
    response = client.post(
        "/api/v1/schools",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Duplicate", "slug": "dup-school"},
    )
    assert response.status_code == 409


def test_create_school_returns_403_for_non_admin(client, seeded_users):
    """
    Validate school creation forbidden for non-admin.

    1. Build student school-scoped header.
    2. Call create school endpoint once.
    3. Receive forbidden response.
    4. Validate non-admin cannot create schools.
    """
    response = client.post(
        "/api/v1/schools",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
        json={"name": "Forbidden", "slug": "forbidden-school"},
    )
    assert response.status_code == 403


def test_update_school_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate school update success for admin.

    1. Seed a school and add admin membership for same school.
    2. Call update school endpoint once.
    3. Receive successful response.
    4. Validate updated name field.
    """
    school = create_school(db_session, "To Update", "to-update")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.put(
        f"/api/v1/schools/{school.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), school.id),
        json={"name": "Updated School"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated School"


def test_update_school_returns_400_for_mismatched_header(client, seeded_users, db_session):
    """
    Validate school update header/path mismatch branch.

    1. Seed school and admin membership.
    2. Call update endpoint with different school id header.
    3. Receive bad request response.
    4. Validate path/header mismatch is rejected.
    """
    school = create_school(db_session, "Mismatch", "mismatch")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.put(
        f"/api/v1/schools/{school.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Mismatch"},
    )
    assert response.status_code == 400


def test_update_school_returns_404_for_missing_school(client, seeded_users):
    """
    Validate school update missing-school branch.

    1. Build admin header matching missing school id.
    2. Call update endpoint with non-existing id.
    3. Receive not found response.
    4. Validate missing schools return 404.
    """
    response = client.put(
        "/api/v1/schools/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), 999999),
        json={"name": "Missing"},
    )
    assert response.status_code == 404


def test_associate_user_to_school_returns_201_for_admin(client, seeded_users):
    """
    Validate user-school association success.

    1. Build admin school-scoped header.
    2. Call school-user association endpoint once.
    3. Receive created response.
    4. Validate status code is 201.
    """
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"user_id": seeded_users["teacher"].id, "role": "admin"},
    )
    assert response.status_code == 201


def test_associate_user_to_school_returns_404_for_missing_user(client, seeded_users):
    """
    Validate user-school association missing-user branch.

    1. Build admin school-scoped header.
    2. Call association endpoint with unknown user id.
    3. Receive not found response.
    4. Validate missing user returns 404.
    """
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"user_id": 999999, "role": "teacher"},
    )
    assert response.status_code == 404


def test_deassociate_user_from_school_returns_204_for_admin(client, seeded_users):
    """
    Validate user-school deassociation success.

    1. Build admin school-scoped header.
    2. Call deassociation endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    response = client.delete(
        f"/api/v1/schools/{seeded_users['north_school'].id}/users/{seeded_users['teacher'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_delete_school_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate school deletion success for admin.

    1. Seed school and add admin membership.
    2. Call delete school endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    school = create_school(db_session, "Delete School", "delete-school")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.delete(
        f"/api/v1/schools/{school.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), school.id),
    )
    assert response.status_code == 204


def test_delete_school_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate school deletion header/path mismatch branch.

    1. Build admin header for different school id.
    2. Call delete school endpoint once.
    3. Receive bad request response.
    4. Validate path/header mismatch is rejected.
    """
    response = client.delete(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400
