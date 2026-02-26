from decimal import Decimal

from app.domain.fee_recurrence import FeeRecurrence
from app.infrastructure.db.models import FeeDefinition
from tests.helpers.auth import school_header, token_for_user


def _create_fee(db_session, school_id: int, name: str, amount: str, recurrence: FeeRecurrence) -> FeeDefinition:
    fee = FeeDefinition(
        school_id=school_id,
        name=name,
        amount=Decimal(amount),
        recurrence=recurrence,
        is_active=True,
    )
    db_session.add(fee)
    db_session.commit()
    db_session.refresh(fee)
    return fee


def test_get_fees_returns_401_without_token(client):
    """
    Validate fees list unauthorized branch.

    1. Call fees list endpoint without auth header.
    2. Receive error response.
    3. Validate unauthorized status code.
    4. Validate endpoint requires authentication.
    """
    response = client.get("/api/v1/fees")
    assert response.status_code == 401


def test_get_fees_returns_403_for_non_admin(client, seeded_users):
    """
    Validate fees list forbidden for non-admin members.

    1. Build non-admin token and school header.
    2. Call fees list endpoint once.
    3. Receive forbidden response.
    4. Validate admin role requirement is enforced.
    """
    response = client.get(
        "/api/v1/fees",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 403


def test_get_fees_returns_paginated_envelope_for_admin(client, seeded_users, db_session):
    """
    Validate fees list success envelope for admins.

    1. Seed one fee in active school.
    2. Call fees list endpoint once with admin credentials.
    3. Receive successful paginated response.
    4. Validate payload contains items and pagination keys.
    """
    _create_fee(db_session, seeded_users["north_school"].id, "Cuota mensual", "150.00", FeeRecurrence.monthly)
    response = client.get(
        "/api/v1/fees",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["pagination"]["offset"] == 0
    assert payload["pagination"]["limit"] == 20


def test_get_fees_applies_limit_offset_and_search(client, seeded_users, db_session):
    """
    Validate fees list pagination and search behavior.

    1. Seed two fees in active school with different names.
    2. Call fees list endpoint with search and pagination query.
    3. Receive successful response payload.
    4. Validate result set matches filtered and paged expectation.
    """
    _create_fee(db_session, seeded_users["north_school"].id, "Needle Fee", "100.00", FeeRecurrence.monthly)
    _create_fee(db_session, seeded_users["north_school"].id, "Other Fee", "120.00", FeeRecurrence.annual)
    response = client.get(
        "/api/v1/fees?search=needle&offset=0&limit=1",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["name"] == "Needle Fee"
    assert payload["pagination"]["filtered_total"] == 1


def test_create_fee_returns_201_for_admin(client, seeded_users):
    """
    Validate fee creation success for admin users.

    1. Build admin school-scoped header.
    2. Call create fee endpoint once.
    3. Receive created response payload.
    4. Validate created fee name and recurrence.
    """
    response = client.post(
        "/api/v1/fees",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Matrícula", "amount": "450.00", "recurrence": "annual", "is_active": True},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Matrícula"
    assert response.json()["recurrence"] == "annual"


def test_create_fee_returns_409_for_duplicate_natural_key(client, seeded_users, db_session):
    """
    Validate fee creation duplicate conflict branch.

    1. Seed fee with target natural key in active school.
    2. Call create fee endpoint with same key.
    3. Receive conflict response.
    4. Validate duplicate creation is rejected.
    """
    _create_fee(db_session, seeded_users["north_school"].id, "Materiales", "95.00", FeeRecurrence.one_time)
    response = client.post(
        "/api/v1/fees",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Materiales", "amount": "120.00", "recurrence": "one_time", "is_active": True},
    )
    assert response.status_code == 409


def test_get_fee_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate fee get-by-id success for admin users.

    1. Seed one fee in active school.
    2. Call get fee endpoint once.
    3. Receive successful response payload.
    4. Validate returned id matches seeded fee.
    """
    fee = _create_fee(db_session, seeded_users["north_school"].id, "Books", "55.00", FeeRecurrence.one_time)
    response = client.get(
        f"/api/v1/fees/{fee.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == fee.id


def test_get_fee_returns_404_for_missing_fee(client, seeded_users):
    """
    Validate fee get-by-id missing branch.

    1. Build admin school-scoped header.
    2. Call get fee endpoint with unknown id.
    3. Receive not found response.
    4. Validate missing fees return 404.
    """
    response = client.get(
        "/api/v1/fees/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_fee_returns_404_for_fee_in_other_school(client, seeded_users, db_session):
    """
    Validate fee get-by-id tenant isolation branch.

    1. Seed fee in different school.
    2. Call get fee endpoint from active school context.
    3. Receive not found response.
    4. Validate cross-tenant fee is hidden.
    """
    fee = _create_fee(db_session, seeded_users["south_school"].id, "South Fee", "77.00", FeeRecurrence.monthly)
    response = client.get(
        f"/api/v1/fees/{fee.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_update_fee_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate fee update success for admin users.

    1. Seed fee in active school.
    2. Call update fee endpoint once.
    3. Receive successful response payload.
    4. Validate updated values are returned.
    """
    fee = _create_fee(db_session, seeded_users["north_school"].id, "Transport", "60.00", FeeRecurrence.monthly)
    response = client.put(
        f"/api/v1/fees/{fee.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Transportation", "amount": "65.00", "recurrence": "annual", "is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Transportation"
    assert response.json()["recurrence"] == "annual"
    assert response.json()["is_active"] is False


def test_update_fee_returns_404_for_missing_fee(client, seeded_users):
    """
    Validate fee update missing branch.

    1. Build admin school-scoped header.
    2. Call update endpoint with unknown fee id.
    3. Receive not found response.
    4. Validate missing fees return 404.
    """
    response = client.put(
        "/api/v1/fees/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Missing"},
    )
    assert response.status_code == 404


def test_delete_fee_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate fee delete success for admin users.

    1. Seed fee in active school.
    2. Call delete endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    fee = _create_fee(db_session, seeded_users["north_school"].id, "Delete Fee", "80.00", FeeRecurrence.one_time)
    response = client.delete(
        f"/api/v1/fees/{fee.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_delete_fee_returns_404_for_missing_fee(client, seeded_users):
    """
    Validate fee delete missing branch.

    1. Build admin school-scoped header.
    2. Call delete endpoint with unknown fee id.
    3. Receive not found response.
    4. Validate missing fees return 404.
    """
    response = client.delete(
        "/api/v1/fees/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404
