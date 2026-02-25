from tests.helpers.auth import school_header, token_for_user
from tests.helpers.factories import create_student, link_student_school, link_user_student


def test_get_students_returns_200_for_school_admin(client, seeded_users):
    """
    Validate students list success for admin member.

    1. Build admin school-scoped header.
    2. Call students list endpoint once.
    3. Receive successful response.
    4. Validate payload uses paginated envelope.
    """
    response = client.get(
        "/api/v1/students",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["pagination"]["offset"] == 0
    assert payload["pagination"]["limit"] == 20


def test_get_students_returns_200_for_non_admin_with_associations(client, seeded_users):
    """
    Validate students list for non-admin associated user.

    1. Build student school-scoped header.
    2. Call students list endpoint once.
    3. Receive successful response.
    4. Validate seeded associated student appears.
    """
    response = client.get(
        "/api/v1/students",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert seeded_users["child_one"].id in ids


def test_get_students_applies_limit_and_offset(client, seeded_users, db_session):
    """
    Validate students list pagination slicing for admins.

    1. Seed additional students linked to active school.
    2. Call students list endpoint with offset and limit once.
    3. Receive successful paginated response.
    4. Validate item count and pagination metadata.
    """
    student_one = create_student(db_session, "Paginated", "One", "PAG-001")
    student_two = create_student(db_session, "Paginated", "Two", "PAG-002")
    link_student_school(db_session, student_one.id, seeded_users["north_school"].id)
    link_student_school(db_session, student_two.id, seeded_users["north_school"].id)
    response = client.get(
        "/api/v1/students?offset=1&limit=1",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["pagination"]["offset"] == 1
    assert payload["pagination"]["limit"] == 1
    assert payload["pagination"]["filtered_total"] >= 3


def test_get_students_applies_search_on_configured_fields(client, seeded_users, db_session):
    """
    Validate students list search filtering behavior.

    1. Seed one matching and one non-matching student in active school.
    2. Call students list endpoint with search param once.
    3. Receive successful paginated response.
    4. Validate only matching student is returned.
    """
    matching = create_student(db_session, "Needle", "Kid", "SEARCH-001")
    non_matching = create_student(db_session, "Other", "Kid", "SEARCH-002")
    link_student_school(db_session, matching.id, seeded_users["north_school"].id)
    link_student_school(db_session, non_matching.id, seeded_users["north_school"].id)
    response = client.get(
        "/api/v1/students?search=needle",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    first_names = {item["first_name"] for item in payload["items"]}
    assert "Needle" in first_names
    assert "Other" not in first_names
    assert payload["pagination"]["filtered_total"] <= payload["pagination"]["total"]


def test_get_students_returns_403_for_user_without_school_membership(client, seeded_users):
    """
    Validate students list forbidden for users without school access.

    1. Build student token with inaccessible school header.
    2. Call students list endpoint once.
    3. Receive forbidden response.
    4. Validate membership guard is enforced.
    """
    response = client.get(
        "/api/v1/students",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 403


def test_create_student_returns_201_for_admin(client, seeded_users):
    """
    Validate student creation success for admin.

    1. Build admin school-scoped header.
    2. Call student creation endpoint once.
    3. Receive created response.
    4. Validate returned external id.
    """
    response = client.post(
        "/api/v1/students",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"first_name": "Endpoint", "last_name": "Student", "external_id": "EP-001"},
    )
    assert response.status_code == 201
    assert response.json()["external_id"] == "EP-001"


def test_create_student_returns_409_for_duplicate_external_id(client, seeded_users):
    """
    Validate student creation duplicate external id conflict.

    1. Build admin school-scoped header.
    2. Call student creation endpoint with existing external id.
    3. Receive conflict response.
    4. Validate duplicate external id is rejected.
    """
    response = client.post(
        "/api/v1/students",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"first_name": "Dup", "last_name": "Student", "external_id": "STU-001"},
    )
    assert response.status_code == 409


def test_create_student_returns_403_for_non_admin(client, seeded_users):
    """
    Validate student creation forbidden for non-admin.

    1. Build student school-scoped header.
    2. Call student creation endpoint once.
    3. Receive forbidden response.
    4. Validate admin role requirement is enforced.
    """
    response = client.post(
        "/api/v1/students",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
        json={"first_name": "No", "last_name": "Access"},
    )
    assert response.status_code == 403


def test_get_student_returns_200_for_admin(client, seeded_users):
    """
    Validate student get-by-id success for admin.

    1. Build admin school-scoped header.
    2. Call get student endpoint once.
    3. Receive successful response.
    4. Validate returned student id.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == seeded_users["child_one"].id


def test_get_student_returns_association_refs_in_payload(client, seeded_users):
    """
    Validate student get-by-id includes association ids.

    1. Build admin school-scoped header.
    2. Call get student endpoint once.
    3. Receive successful response payload.
    4. Validate school/user ids and references are present.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert "school_ids" in response.json()
    assert "user_ids" in response.json()
    assert "schools" in response.json()
    assert "users" in response.json()


def test_get_student_returns_200_for_associated_non_admin(client, seeded_users):
    """
    Validate student get-by-id success for associated non-admin.

    1. Build associated student user school-scoped header.
    2. Call get student endpoint for linked student once.
    3. Receive successful response.
    4. Validate returned student id.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == seeded_users["child_one"].id


def test_get_student_returns_404_for_existing_student_not_visible_to_user(client, seeded_users):
    """
    Validate student get-by-id hidden student branch.

    1. Build non-admin user header without association to target student.
    2. Call get student endpoint once for existing student.
    3. Receive not found response.
    4. Validate hidden records return 404.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_student_returns_404_for_missing_student(client, seeded_users):
    """
    Validate student get-by-id missing branch.

    1. Build admin school-scoped header.
    2. Call get student endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing students return 404.
    """
    response = client.get(
        "/api/v1/students/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_update_student_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate student update success for admin.

    1. Seed student and link to active school.
    2. Call update endpoint once.
    3. Receive successful response.
    4. Validate updated first_name value.
    """
    student = create_student(db_session, "Update", "Target", "UPD-EP-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    response = client.put(
        f"/api/v1/students/{student.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"first_name": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


def test_update_student_applies_association_sync_payload(client, seeded_users, db_session):
    """
    Validate student update applies association add/remove payload.

    1. Seed student with one user link and one school link.
    2. Call update endpoint with association add/remove payload.
    3. Receive successful response payload.
    4. Validate updated association ids reflect requested delta.
    """
    student = create_student(db_session, "Assoc", "Target", "ASSOC-EP-001")
    other_school = seeded_users["south_school"]
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    link_user_student(db_session, seeded_users["teacher"].id, student.id)
    response = client.put(
        f"/api/v1/students/{student.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "associations": {
                "add": {"user_ids": [seeded_users["student"].id], "school_ids": [other_school.id]},
                "remove": {"user_ids": [seeded_users["teacher"].id], "school_ids": [seeded_users["north_school"].id]},
            }
        },
    )
    assert response.status_code == 200
    assert seeded_users["teacher"].id not in response.json()["user_ids"]
    assert seeded_users["student"].id in response.json()["user_ids"]
    assert seeded_users["north_school"].id not in response.json()["school_ids"]
    assert other_school.id in response.json()["school_ids"]


def test_update_student_returns_404_for_missing_student(client, seeded_users):
    """
    Validate student update missing branch.

    1. Build admin school-scoped header.
    2. Call update endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing students return 404.
    """
    response = client.put(
        "/api/v1/students/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"first_name": "Missing"},
    )
    assert response.status_code == 404


def test_delete_student_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate student delete success for admin.

    1. Seed student and link to active school.
    2. Call delete endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    student = create_student(db_session, "Delete", "Target", "DEL-EP-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    response = client.delete(
        f"/api/v1/students/{student.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_delete_student_returns_404_for_missing_student(client, seeded_users):
    """
    Validate student delete missing branch.

    1. Build admin school-scoped header.
    2. Call delete endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing students return 404.
    """
    response = client.delete(
        "/api/v1/students/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_associate_student_user_returns_201_for_admin(client, seeded_users, db_session):
    """
    Validate student-user association success.

    1. Seed student linked to active school.
    2. Call associate user endpoint once.
    3. Receive created response.
    4. Validate status code is 201.
    """
    student = create_student(db_session, "Assoc", "User", "AUS-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    response = client.post(
        f"/api/v1/students/{student.id}/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"user_id": seeded_users["student"].id},
    )
    assert response.status_code == 201


def test_associate_student_user_returns_404_for_missing_student(client, seeded_users):
    """
    Validate student-user association missing student branch.

    1. Build admin school-scoped header.
    2. Call associate user endpoint with unknown student id.
    3. Receive not found response.
    4. Validate missing student returns 404.
    """
    response = client.post(
        "/api/v1/students/999999/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"user_id": seeded_users["student"].id},
    )
    assert response.status_code == 404


def test_deassociate_student_user_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate student-user deassociation success.

    1. Seed student link with user in active school.
    2. Call deassociate user endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    student = create_student(db_session, "Deassoc", "User", "DAU-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    link_user_student(db_session, seeded_users["student"].id, student.id)
    response = client.delete(
        f"/api/v1/students/{student.id}/users/{seeded_users['student'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_associate_student_school_returns_201_for_admin(client, seeded_users, db_session):
    """
    Validate student-school association success.

    1. Seed student linked to north school.
    2. Call association endpoint for south school.
    3. Receive created response.
    4. Validate status code is 201.
    """
    student = create_student(db_session, "Assoc", "School", "ASS-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    response = client.post(
        f"/api/v1/students/{student.id}/schools",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"school_id": seeded_users["south_school"].id},
    )
    assert response.status_code == 201


def test_associate_student_school_returns_409_for_duplicate_link(client, seeded_users, db_session):
    """
    Validate student-school association duplicate branch.

    1. Seed student linked to active school.
    2. Call association endpoint with same school id.
    3. Receive conflict response.
    4. Validate duplicate association is rejected.
    """
    student = create_student(db_session, "Dup", "School", "ASS-002")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    response = client.post(
        f"/api/v1/students/{student.id}/schools",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"school_id": seeded_users["north_school"].id},
    )
    assert response.status_code == 409


def test_deassociate_student_school_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate student-school deassociation success.

    1. Seed student linked to active school.
    2. Call deassociation endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    student = create_student(db_session, "Deassoc", "School", "DAS-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    response = client.delete(
        f"/api/v1/students/{student.id}/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204
