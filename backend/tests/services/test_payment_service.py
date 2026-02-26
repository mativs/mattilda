from datetime import date, datetime, timezone

import pytest

from app.application.errors import NotFoundError, ValidationError
from app.application.services.payment_service import (
    build_visible_payments_query_for_student,
    create_payment,
    get_invoice_in_school,
    get_student_in_school,
    get_visible_payment_by_id,
    get_visible_student_for_payment_access,
    serialize_payment_response,
)
from app.interfaces.api.v1.schemas.payment import PaymentCreate
from tests.helpers.factories import (
    create_invoice,
    create_payment as factory_create_payment,
    create_school,
    create_student,
    create_user,
    link_student_school,
    link_user_student,
)


def test_get_student_in_school_returns_student_when_linked(db_session):
    """
    Validate student lookup within school context succeeds.

    1. Seed one school and one linked student.
    2. Call student-in-school helper once.
    3. Validate returned entity is a student.
    4. Validate returned id matches seeded student.
    """
    school = create_school(db_session, "North Payment", "north-payment")
    student = create_student(db_session, "Pay", "Kid", "PAY-STU-001")
    link_student_school(db_session, student.id, school.id)
    found = get_student_in_school(db_session, student_id=student.id, school_id=school.id)
    assert found.id == student.id


def test_get_student_in_school_raises_not_found_for_missing_link(db_session):
    """
    Validate student lookup raises for missing school link.

    1. Seed one school and one unlinked student.
    2. Call student-in-school helper once.
    3. Validate helper raises NotFoundError.
    4. Validate error message matches expected value.
    """
    school = create_school(db_session, "North Missing", "north-missing-payment")
    student = create_student(db_session, "No", "Link", "PAY-STU-002")
    with pytest.raises(NotFoundError) as exc:
        get_student_in_school(db_session, student_id=student.id, school_id=school.id)
    assert str(exc.value) == "Student not found"


def test_get_invoice_in_school_raises_not_found_for_other_school(db_session):
    """
    Validate invoice lookup is school-scoped.

    1. Seed two schools and one invoice in school A.
    2. Call invoice-in-school helper with school B context.
    3. Validate helper raises NotFoundError.
    4. Validate cross-school access is blocked.
    """
    school_a = create_school(db_session, "North A", "north-a-payment")
    school_b = create_school(db_session, "North B", "north-b-payment")
    student = create_student(db_session, "Inv", "Kid", "PAY-STU-003")
    link_student_school(db_session, student.id, school_a.id)
    invoice = create_invoice(
        db_session,
        school_id=school_a.id,
        student_id=student.id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        total_amount="100.00",
    )
    with pytest.raises(NotFoundError):
        get_invoice_in_school(db_session, invoice_id=invoice.id, school_id=school_b.id)


def test_create_payment_persists_without_invoice(db_session):
    """
    Validate payment creation works without invoice reference.

    1. Seed school and linked student.
    2. Call create payment with nullable invoice_id.
    3. Validate returned payment fields are persisted.
    4. Validate invoice_id remains null.
    """
    school = create_school(db_session, "North Create", "north-create-payment")
    student = create_student(db_session, "Create", "Pay", "PAY-STU-004")
    link_student_school(db_session, student.id, school.id)
    created = create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=None,
            amount="40.00",
            paid_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
            method="cash",
        ),
    )
    assert created.student_id == student.id
    assert created.invoice_id is None
    assert str(created.amount) == "40.00"


def test_create_payment_raises_validation_when_invoice_mismatches_student(db_session):
    """
    Validate payment creation rejects invoice-student mismatch.

    1. Seed school with two linked students and one invoice for student A.
    2. Call create payment for student B using invoice from student A.
    3. Validate service raises ValidationError.
    4. Validate message explains invoice ownership mismatch.
    """
    school = create_school(db_session, "North Validate", "north-validate-payment")
    student_a = create_student(db_session, "A", "Pay", "PAY-STU-005")
    student_b = create_student(db_session, "B", "Pay", "PAY-STU-006")
    link_student_school(db_session, student_a.id, school.id)
    link_student_school(db_session, student_b.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student_a.id,
        period="2026-04",
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        due_date=date(2026, 4, 10),
        total_amount="120.00",
    )
    with pytest.raises(ValidationError) as exc:
        create_payment(
            db_session,
            school_id=school.id,
            payload=PaymentCreate(
                student_id=student_b.id,
                invoice_id=invoice.id,
                amount="10.00",
                paid_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
                method="transfer",
            ),
        )
    assert str(exc.value) == "Invoice does not belong to student"


def test_visibility_helpers_filter_non_admin_access(db_session):
    """
    Validate payment visibility helpers enforce student association.

    1. Seed one school, student, payment, and two users.
    2. Associate only one user to the student.
    3. Query visibility helpers for associated and non-associated users.
    4. Validate non-associated user cannot resolve student/payment.
    """
    school = create_school(db_session, "North Visibility", "north-visibility-payment")
    student = create_student(db_session, "Visible", "Pay", "PAY-STU-007")
    associated_user = create_user(db_session, "associated-payment@example.com")
    hidden_user = create_user(db_session, "hidden-payment@example.com")
    link_student_school(db_session, student.id, school.id)
    link_user_student(db_session, associated_user.id, student.id)
    payment = factory_create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        amount="55.00",
        paid_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
    )
    visible_student = get_visible_student_for_payment_access(
        db_session,
        student_id=student.id,
        school_id=school.id,
        user_id=associated_user.id,
        is_admin=False,
    )
    hidden_student = get_visible_student_for_payment_access(
        db_session,
        student_id=student.id,
        school_id=school.id,
        user_id=hidden_user.id,
        is_admin=False,
    )
    hidden_payment = get_visible_payment_by_id(
        db_session,
        payment_id=payment.id,
        school_id=school.id,
        user_id=hidden_user.id,
        is_admin=False,
    )
    assert visible_student is not None
    assert hidden_student is None
    assert hidden_payment is None


def test_build_visible_payments_query_and_serialize_response(db_session):
    """
    Validate payment list query and serializer output shape.

    1. Seed school, student, invoice, and one payment.
    2. Execute visible payment query as admin.
    3. Serialize first result once.
    4. Validate payload includes student and invoice references.
    """
    school = create_school(db_session, "North Serialize", "north-serialize-payment")
    student = create_student(db_session, "Serialize", "Pay", "PAY-STU-008")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-06",
        issued_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        due_date=date(2026, 6, 10),
        total_amount="80.00",
    )
    factory_create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        amount="80.00",
        paid_at=datetime(2026, 6, 11, tzinfo=timezone.utc),
        method="card",
    )
    query = build_visible_payments_query_for_student(
        student_id=student.id,
        school_id=school.id,
        user_id=0,
        is_admin=True,
    )
    rows = list(db_session.execute(query).scalars().all())
    payload = serialize_payment_response(rows[0])
    assert payload["student"]["id"] == student.id
    assert payload["invoice"]["id"] == invoice.id
    assert payload["method"] == "card"
