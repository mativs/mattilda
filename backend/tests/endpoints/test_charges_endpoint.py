from datetime import date

from app.domain.charge_enums import ChargeStatus, ChargeType
from tests.helpers.auth import school_header, token_for_user
from tests.helpers.factories import create_charge, create_student, link_student_school


def test_get_charges_returns_401_without_token(client):
    """
    Validate charges list unauthorized branch.

    1. Call charges list endpoint without auth header.
    2. Receive error response.
    3. Validate unauthorized status code.
    4. Validate endpoint requires authentication.
    """
    response = client.get("/api/v1/charges")
    assert response.status_code == 401


def test_get_charges_returns_403_for_non_admin(client, seeded_users):
    """
    Validate charges list forbidden for non-admin users.

    1. Build non-admin school-scoped header.
    2. Call charges list endpoint once.
    3. Receive forbidden response.
    4. Validate admin role requirement is enforced.
    """
    response = client.get(
        "/api/v1/charges",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 403


def test_get_charges_returns_paginated_envelope_for_admin(client, seeded_users, db_session):
    """
    Validate charges list success envelope for admins.

    1. Seed one charge in active school.
    2. Call charges list endpoint once with admin credentials.
    3. Receive successful paginated response.
    4. Validate payload has items and pagination metadata.
    """
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Cuota abril",
        amount="150.00",
        due_date=date(2026, 4, 10),
    )
    response = client.get(
        "/api/v1/charges",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["pagination"]["offset"] == 0
    assert payload["pagination"]["limit"] == 20


def test_get_charges_applies_search_with_student_name(client, seeded_users, db_session):
    """
    Validate charges list search by student name.

    1. Seed charges tied to distinct students in same school.
    2. Call charges list endpoint with student-name search term.
    3. Receive successful filtered response.
    4. Validate only matching student's charge appears.
    """
    other_student = create_student(db_session, "Needle", "Target", "CHG-SEARCH-001")
    link_student_school(db_session, other_student.id, seeded_users["north_school"].id)
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=other_student.id,
        description="Needle charge",
        amount="25.00",
        due_date=date(2026, 4, 12),
    )
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Other charge",
        amount="35.00",
        due_date=date(2026, 4, 13),
    )
    response = client.get(
        "/api/v1/charges?search=needle",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["student"]["first_name"] == "Needle"


def test_create_charge_returns_201_for_admin(client, seeded_users):
    """
    Validate charge creation success for admin users.

    1. Build admin school-scoped header.
    2. Call create charge endpoint once.
    3. Receive created response payload.
    4. Validate persisted student and status values.
    """
    response = client.post(
        "/api/v1/charges",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "student_id": seeded_users["child_one"].id,
            "fee_definition_id": None,
            "description": "New charge",
            "amount": "44.00",
            "period": "2026-04",
            "debt_created_at": "2026-04-01T09:00:00Z",
            "due_date": "2026-04-20",
            "charge_type": "fee",
            "status": "unpaid",
        },
    )
    assert response.status_code == 201
    assert response.json()["student_id"] == seeded_users["child_one"].id
    assert response.json()["status"] == "unpaid"


def test_create_charge_returns_404_for_missing_student(client, seeded_users):
    """
    Validate charge creation missing-student branch.

    1. Build admin school-scoped header.
    2. Call create charge endpoint with unknown student id.
    3. Receive not found response.
    4. Validate invalid student is rejected.
    """
    response = client.post(
        "/api/v1/charges",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "student_id": 999999,
            "fee_definition_id": None,
            "description": "Invalid student charge",
            "amount": "44.00",
            "period": None,
            "debt_created_at": "2026-04-01T09:00:00Z",
            "due_date": "2026-04-20",
            "charge_type": "fee",
            "status": "unpaid",
        },
    )
    assert response.status_code == 404


def test_get_charge_returns_404_for_other_school_record(client, seeded_users, db_session):
    """
    Validate charge get-by-id tenant isolation branch.

    1. Seed charge in different school context.
    2. Call get charge endpoint from active school.
    3. Receive not found response.
    4. Validate cross-tenant charge is hidden.
    """
    charge = create_charge(
        db_session,
        school_id=seeded_users["south_school"].id,
        student_id=seeded_users["child_two"].id,
        description="South charge",
        amount="88.00",
        due_date=date(2026, 4, 21),
    )
    response = client.get(
        f"/api/v1/charges/{charge.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_charge_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate charge get-by-id success for admin users.

    1. Seed one charge in active school.
    2. Call get charge endpoint once.
    3. Receive successful response payload.
    4. Validate returned id matches seeded charge.
    """
    charge = create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Visible charge",
        amount="19.00",
        due_date=date(2026, 4, 28),
    )
    response = client.get(
        f"/api/v1/charges/{charge.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == charge.id


def test_get_charge_returns_404_for_missing_charge(client, seeded_users):
    """
    Validate charge get-by-id missing branch.

    1. Build admin school-scoped header.
    2. Call get charge endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing charges return 404.
    """
    response = client.get(
        "/api/v1/charges/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_update_charge_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate charge update success for admin users.

    1. Seed one charge in active school.
    2. Call update charge endpoint once.
    3. Receive successful response payload.
    4. Validate updated description and status.
    """
    charge = create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="To update",
        amount="66.00",
        due_date=date(2026, 4, 22),
    )
    response = client.put(
        f"/api/v1/charges/{charge.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"description": "Updated charge", "status": "paid", "charge_type": "interest"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated charge"
    assert response.json()["status"] == "paid"


def test_update_charge_returns_404_for_missing_charge(client, seeded_users):
    """
    Validate charge update missing branch.

    1. Build admin school-scoped header.
    2. Call update charge endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing charges return 404.
    """
    response = client.put(
        "/api/v1/charges/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"description": "Missing charge"},
    )
    assert response.status_code == 404


def test_delete_charge_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate charge delete success for admin users.

    1. Seed one charge in active school.
    2. Call delete endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    charge = create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="To delete",
        amount="77.00",
        due_date=date(2026, 4, 23),
    )
    response = client.delete(
        f"/api/v1/charges/{charge.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_delete_charge_returns_404_for_missing_charge(client, seeded_users):
    """
    Validate charge delete missing branch.

    1. Build admin school-scoped header.
    2. Call delete charge endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing charges return 404.
    """
    response = client.delete(
        "/api/v1/charges/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_student_unpaid_charges_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate student unpaid charges summary success for admin.

    1. Seed two unpaid charges and one paid charge for student.
    2. Call student unpaid endpoint once as admin.
    3. Receive successful summary payload.
    4. Validate item count and total amount include only unpaid charges.
    """
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Unpaid A",
        amount="10.00",
        due_date=date(2026, 4, 24),
        status=ChargeStatus.unpaid,
        charge_type=ChargeType.fee,
    )
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Paid B",
        amount="20.00",
        due_date=date(2026, 4, 25),
        status=ChargeStatus.paid,
        charge_type=ChargeType.fee,
    )
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Unpaid C",
        amount="5.50",
        due_date=date(2026, 4, 26),
        status=ChargeStatus.unpaid,
        charge_type=ChargeType.interest,
    )
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/charges/unpaid?offset=0&limit=1&search=unpaid",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["pagination"]["offset"] == 0
    assert response.json()["pagination"]["limit"] == 1
    assert response.json()["pagination"]["filtered_total"] == 2
    assert response.json()["total_unpaid_amount"] == "15.50"


def test_get_student_unpaid_charges_returns_404_for_non_visible_non_admin(client, seeded_users):
    """
    Validate student unpaid charges hidden for non-associated non-admin users.

    1. Build non-admin user header without association to target student.
    2. Call student unpaid endpoint once.
    3. Receive not found response.
    4. Validate endpoint enforces student visibility rules.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/charges/unpaid",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_student_unpaid_charges_returns_200_for_visible_non_admin(client, seeded_users):
    """
    Validate student unpaid charges success for associated non-admin users.

    1. Build associated non-admin school-scoped header.
    2. Call student unpaid endpoint once.
    3. Receive successful response.
    4. Validate response includes pagination metadata.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/charges/unpaid",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert "pagination" in response.json()
