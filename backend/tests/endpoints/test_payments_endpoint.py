from datetime import date, datetime, timezone

from tests.helpers.auth import school_header, token_for_user
from tests.helpers.factories import (
    create_invoice,
    create_payment,
    create_student,
    link_student_school,
    link_user_student,
)


def test_create_payment_returns_201_for_admin(client, seeded_users, db_session):
    """
    Validate payment creation succeeds for school admin.

    1. Seed one invoice for an existing student in active school.
    2. Call create payment endpoint once as admin.
    3. Receive created response payload.
    4. Validate payment fields and invoice reference are returned.
    """
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        total_amount="150.00",
    )
    response = client.post(
        "/api/v1/payments",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "student_id": seeded_users["child_one"].id,
            "invoice_id": invoice.id,
            "amount": "75.00",
            "paid_at": "2026-03-08T12:00:00Z",
            "method": "transfer",
        },
    )
    assert response.status_code == 201
    assert response.json()["student_id"] == seeded_users["child_one"].id
    assert response.json()["invoice"]["id"] == invoice.id


def test_create_payment_returns_403_for_non_admin(client, seeded_users):
    """
    Validate payment creation is forbidden for non-admin users.

    1. Build non-admin school-scoped header.
    2. Call create payment endpoint once.
    3. Receive forbidden response.
    4. Validate admin-only create policy is enforced.
    """
    response = client.post(
        "/api/v1/payments",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
        json={
            "student_id": seeded_users["child_one"].id,
            "invoice_id": None,
            "amount": "20.00",
            "paid_at": "2026-03-08T12:00:00Z",
            "method": "cash",
        },
    )
    assert response.status_code == 403


def test_create_payment_returns_400_for_invoice_student_mismatch(client, seeded_users, db_session):
    """
    Validate payment creation rejects mismatched invoice/student payload.

    1. Seed invoice belonging to a different student in active school.
    2. Call create payment endpoint once with mismatched student id.
    3. Receive bad-request response.
    4. Validate validation error is surfaced.
    """
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_two"].id,
        period="2026-04",
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        due_date=date(2026, 4, 10),
        total_amount="100.00",
    )
    response = client.post(
        "/api/v1/payments",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={
            "student_id": seeded_users["child_one"].id,
            "invoice_id": invoice.id,
            "amount": "10.00",
            "paid_at": "2026-04-04T10:00:00Z",
            "method": "card",
        },
    )
    assert response.status_code == 400


def test_get_student_payments_returns_paginated_envelope_for_admin(client, seeded_users, db_session):
    """
    Validate student payments list returns paginated envelope.

    1. Seed one payment for target student in active school.
    2. Call student payments list endpoint once as admin.
    3. Receive successful response payload.
    4. Validate items list and pagination metadata exist.
    """
    create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="50.00",
        paid_at=datetime(2026, 3, 7, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/payments",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)
    assert response.json()["pagination"]["offset"] == 0


def test_get_student_payments_applies_search(client, seeded_users, db_session):
    """
    Validate student payments list applies search filter.

    1. Seed two payments with different methods for same student.
    2. Call student payments endpoint with search term once.
    3. Receive successful filtered response.
    4. Validate only matching method payment remains.
    """
    create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="10.00",
        paid_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        method="cash",
    )
    create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="15.00",
        paid_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        method="transfer",
    )
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/payments?search=cash",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["method"] == "cash"


def test_get_student_payments_returns_404_for_hidden_student(client, seeded_users):
    """
    Validate student payments list hides non-visible students.

    1. Use teacher token not associated with seeded student.
    2. Call student payments endpoint once.
    3. Receive not-found response.
    4. Validate hidden existing student resolves as 404.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/payments",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_student_payments_returns_200_for_associated_non_admin(client, seeded_users, db_session):
    """
    Validate associated non-admin can list visible student payments.

    1. Seed payment for student associated to seeded student user.
    2. Call student payments endpoint once as non-admin.
    3. Receive successful response.
    4. Validate returned payment belongs to requested student.
    """
    create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="30.00",
        paid_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/payments",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["student_id"] == seeded_users["child_one"].id


def test_get_payment_detail_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate payment detail endpoint returns payment for admin.

    1. Seed one payment in active school.
    2. Call payment detail endpoint once as admin.
    3. Receive successful response payload.
    4. Validate returned id matches seeded payment.
    """
    payment = create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="44.00",
        paid_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/payments/{payment.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == payment.id


def test_get_payment_detail_returns_404_for_hidden_payment(client, seeded_users, db_session):
    """
    Validate payment detail endpoint hides non-visible payment.

    1. Seed payment for student not associated to teacher.
    2. Call payment detail endpoint once as teacher.
    3. Receive not-found response.
    4. Validate hidden existing payment resolves as 404.
    """
    payment = create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="21.00",
        paid_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/payments/{payment.id}",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_payment_detail_returns_200_for_associated_non_admin(client, seeded_users, db_session):
    """
    Validate associated non-admin can read payment detail.

    1. Seed one payment for student associated to seeded student user.
    2. Call payment detail endpoint once as non-admin.
    3. Receive successful response payload.
    4. Validate returned id matches seeded payment.
    """
    payment = create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        amount="60.00",
        paid_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/payments/{payment.id}",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == payment.id


def test_get_payment_detail_returns_404_for_missing_payment(client, seeded_users):
    """
    Validate payment detail endpoint returns not found for unknown id.

    1. Build admin school-scoped header.
    2. Call payment detail endpoint with unknown id.
    3. Receive not-found response.
    4. Validate missing payment branch is covered.
    """
    response = client.get(
        "/api/v1/payments/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_student_payments_returns_400_without_headers(client):
    """
    Validate student payments endpoint requires school header/auth context.

    1. Call student payments endpoint without required headers.
    2. Receive bad-request response.
    3. Validate status code is 400.
    4. Validate school context guard triggers first.
    """
    response = client.get("/api/v1/students/1/payments")
    assert response.status_code == 400


def test_get_student_payments_for_non_admin_requires_association(client, seeded_users, db_session):
    """
    Validate non-admin listing payments for newly associated student.

    1. Seed custom student and payment in active school.
    2. Associate teacher to student and call list endpoint once.
    3. Receive successful response payload.
    4. Validate payment belongs to associated custom student.
    """
    custom_student = create_student(db_session, "Pay", "Assoc", "PAY-EP-001")
    link_student_school(db_session, custom_student.id, seeded_users["north_school"].id)
    link_user_student(db_session, seeded_users["teacher"].id, custom_student.id)
    payment = create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=custom_student.id,
        amount="90.00",
        paid_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/students/{custom_student.id}/payments",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == payment.id
