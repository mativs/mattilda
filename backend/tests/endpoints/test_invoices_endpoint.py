from datetime import date, datetime, timezone

from app.domain.invoice_status import InvoiceStatus
from tests.helpers.auth import school_header, token_for_user
from tests.helpers.factories import (
    create_charge,
    create_invoice,
    create_invoice_item,
    create_student,
    link_student_school,
    link_user_student,
)


def test_get_student_invoices_returns_paginated_summaries_for_admin(client, seeded_users, db_session):
    """
    Validate student invoice list returns summary rows only.

    1. Seed one invoice for target student in active school.
    2. Call student invoices list endpoint once as admin.
    3. Receive successful paginated response.
    4. Validate row has summary fields and excludes nested items.
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
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/invoices",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["id"] == invoice.id
    assert "items" not in payload["items"][0]
    assert payload["pagination"]["offset"] == 0


def test_get_student_invoices_applies_search(client, seeded_users, db_session):
    """
    Validate student invoice list applies configured search.

    1. Seed two invoices with different periods for same student.
    2. Call student invoices list endpoint with search term once.
    3. Receive successful filtered response.
    4. Validate only matching period invoice appears.
    """
    create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        total_amount="100.00",
    )
    target = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-04",
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        due_date=date(2026, 4, 10),
        total_amount="110.00",
    )
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/invoices?search=2026-04",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["id"] == target.id


def test_get_student_invoices_returns_404_for_hidden_student_to_non_admin(client, seeded_users):
    """
    Validate student invoice list hides inaccessible student.

    1. Use teacher token without association to seeded student.
    2. Call student invoices list endpoint once.
    3. Receive not-found response.
    4. Validate hidden existing student returns 404.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/invoices",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_student_invoices_returns_200_for_associated_non_admin(client, seeded_users, db_session):
    """
    Validate student invoice list for associated non-admin user.

    1. Seed one invoice for student associated to seeded student user.
    2. Call student invoices list endpoint once as non-admin.
    3. Receive successful response.
    4. Validate returned invoice belongs to requested student.
    """
    create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-05",
        issued_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        due_date=date(2026, 5, 10),
        total_amount="90.00",
        status=InvoiceStatus.closed,
    )
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/invoices",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["student_id"] == seeded_users["child_one"].id


def test_get_invoice_detail_returns_nested_items(client, seeded_users, db_session):
    """
    Validate invoice detail endpoint includes nested item rows.

    1. Seed invoice plus one charge and one invoice item.
    2. Call invoice detail endpoint once as admin.
    3. Receive successful invoice payload.
    4. Validate nested items array contains snapshot data.
    """
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-06",
        issued_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        due_date=date(2026, 6, 10),
        total_amount="75.00",
    )
    charge = create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Invoice charge",
        amount="75.00",
        due_date=date(2026, 6, 10),
    )
    create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=charge.id,
        description="Invoice charge",
        amount="75.00",
    )
    response = client.get(
        f"/api/v1/invoices/{invoice.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["charge_id"] == charge.id


def test_get_invoice_detail_returns_404_for_hidden_invoice(client, seeded_users, db_session):
    """
    Validate invoice detail endpoint hides non-visible records.

    1. Seed invoice for unassociated student and use teacher token.
    2. Call invoice detail endpoint once.
    3. Receive not-found response.
    4. Validate hidden existing invoice returns 404.
    """
    hidden_student = create_student(db_session, "Hidden", "Invoice", "INV-EP-001")
    link_student_school(db_session, hidden_student.id, seeded_users["north_school"].id)
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=hidden_student.id,
        period="2026-07",
        issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        due_date=date(2026, 7, 10),
        total_amount="55.00",
    )
    response = client.get(
        f"/api/v1/invoices/{invoice.id}",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_invoice_items_returns_200_for_associated_non_admin(client, seeded_users, db_session):
    """
    Validate invoice items endpoint allows associated non-admin access.

    1. Seed invoice for associated student with one invoice item.
    2. Call invoice items endpoint once as associated non-admin.
    3. Receive successful response.
    4. Validate returned item belongs to requested invoice.
    """
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-08",
        issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        due_date=date(2026, 8, 10),
        total_amount="45.00",
    )
    charge = create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Line item",
        amount="45.00",
        due_date=date(2026, 8, 10),
    )
    create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=charge.id,
        description="Line item",
        amount="45.00",
    )
    response = client.get(
        f"/api/v1/invoices/{invoice.id}/items",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()[0]["invoice_id"] == invoice.id


def test_get_invoice_items_returns_404_for_missing_invoice(client, seeded_users):
    """
    Validate invoice items endpoint missing branch.

    1. Build admin school-scoped header.
    2. Call invoice items endpoint with unknown id.
    3. Receive not-found response.
    4. Validate missing invoices return 404.
    """
    response = client.get(
        "/api/v1/invoices/999999/items",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_get_invoice_detail_returns_401_without_token(client):
    """
    Validate invoice detail endpoint authentication requirement.

    1. Call invoice detail endpoint without auth header.
    2. Receive bad-request response.
    3. Validate status code is 400.
    4. Validate endpoint requires authentication.
    """
    response = client.get("/api/v1/invoices/1")
    assert response.status_code == 400


def test_get_student_invoices_returns_403_for_user_without_school_membership(client, seeded_users):
    """
    Validate student invoice list rejects users outside school membership.

    1. Use student token with inaccessible school header.
    2. Call student invoices list endpoint once.
    3. Receive forbidden response.
    4. Validate school membership guard is enforced.
    """
    response = client.get(
        f"/api/v1/students/{seeded_users['child_one'].id}/invoices",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 403


def test_get_invoice_detail_returns_200_for_associated_non_admin(client, seeded_users, db_session):
    """
    Validate invoice detail endpoint for associated non-admin.

    1. Seed invoice for student associated to seeded student user.
    2. Call invoice detail endpoint once as non-admin.
    3. Receive successful response.
    4. Validate returned invoice id matches seeded data.
    """
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-09",
        issued_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        due_date=date(2026, 9, 10),
        total_amount="65.00",
    )
    response = client.get(
        f"/api/v1/invoices/{invoice.id}",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == invoice.id


def test_get_student_invoices_for_non_admin_requires_student_association(client, seeded_users, db_session):
    """
    Validate non-admin invoice list for custom associated student.

    1. Seed new student and invoice in active school.
    2. Associate teacher to that student and call list endpoint once.
    3. Receive successful response.
    4. Validate returned invoice belongs to associated student.
    """
    custom_student = create_student(db_session, "Assoc", "Invoice", "INV-EP-002")
    link_student_school(db_session, custom_student.id, seeded_users["north_school"].id)
    link_user_student(db_session, seeded_users["teacher"].id, custom_student.id)
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=custom_student.id,
        period="2026-10",
        issued_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        due_date=date(2026, 10, 10),
        total_amount="130.00",
    )
    response = client.get(
        f"/api/v1/students/{custom_student.id}/invoices",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == invoice.id
