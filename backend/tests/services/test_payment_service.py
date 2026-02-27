from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.application.errors import NotFoundError, ValidationError
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge, Invoice
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
    list_from_query,
    list_negative_unpaid_carry_for_student,
    create_payment as factory_create_payment,
    create_school,
    create_student,
    create_user,
    get_entity_by_id,
    link_student_school,
    link_user_student,
    persist_entities,
    persist_entity,
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


def test_create_payment_allocates_and_closes_invoice_when_fully_covered(db_session):
    """
    Validate payment creation fully allocates and closes invoice.

    1. Seed school, student, open invoice, and one unpaid positive charge.
    2. Call create payment with enough amount once.
    3. Validate charge becomes paid and invoice closes.
    4. Validate payment persists with linked invoice id.
    """
    school = create_school(db_session, "North Create", "north-create-payment")
    student = create_student(db_session, "Create", "Pay", "PAY-STU-004")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 31),
        total_amount="40.00",
        status=InvoiceStatus.open,
    )
    charge = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Base debt",
        amount=Decimal("40.00"),
        period="2026-03",
        debt_created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    persist_entity(db_session, charge)
    created = create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=invoice.id,
            amount="40.00",
            paid_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
            method="cash",
        ),
    )
    refreshed_charge = get_entity_by_id(db_session, Charge, charge.id)
    refreshed_invoice = get_entity_by_id(db_session, Invoice, invoice.id)
    assert created.invoice_id == invoice.id
    assert refreshed_charge is not None and refreshed_charge.status == ChargeStatus.paid
    assert refreshed_invoice is not None and refreshed_invoice.status == InvoiceStatus.closed


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


def test_create_payment_raises_validation_for_overdue_invoice(db_session):
    """
    Validate payment creation rejects overdue invoices.

    1. Seed school, student, and open overdue invoice.
    2. Call create payment once with paid_at after due date.
    3. Validate service raises ValidationError.
    4. Validate message indicates overdue restriction.
    """
    school = create_school(db_session, "North Overdue", "north-overdue-payment")
    student = create_student(db_session, "Late", "Pay", "PAY-STU-009")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-04",
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        due_date=date(2026, 4, 10),
        total_amount="50.00",
        status=InvoiceStatus.open,
    )
    with pytest.raises(ValidationError) as exc:
        create_payment(
            db_session,
            school_id=school.id,
            payload=PaymentCreate(
                student_id=student.id,
                invoice_id=invoice.id,
                amount="10.00",
                paid_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
                method="transfer",
            ),
        )
    assert str(exc.value) == "Overdue invoices cannot receive payments"


def test_create_payment_raises_validation_for_closed_invoice(db_session):
    """
    Validate payment creation rejects non-open invoices.

    1. Seed school, student, and closed invoice.
    2. Call create payment once for closed invoice.
    3. Validate service raises ValidationError.
    4. Validate message indicates only open invoices are payable.
    """
    school = create_school(db_session, "North Closed", "north-closed-payment")
    student = create_student(db_session, "Closed", "Pay", "PAY-STU-011")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-04",
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        due_date=date(2026, 4, 20),
        total_amount="50.00",
        status=InvoiceStatus.closed,
    )
    with pytest.raises(ValidationError) as exc:
        create_payment(
            db_session,
            school_id=school.id,
            payload=PaymentCreate(
                student_id=student.id,
                invoice_id=invoice.id,
                amount="10.00",
                paid_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
                method="transfer",
            ),
        )
    assert str(exc.value) == "Only open invoices can receive payments"


def test_create_payment_marks_all_positive_charges_paid_when_fully_covered(db_session):
    """
    Validate full coverage branch marks all positive charges as paid.

    1. Seed open invoice with two unpaid positive charges.
    2. Create payment amount greater than total positives.
    3. Reload both charges from database.
    4. Validate both charges are marked paid.
    """
    school = create_school(db_session, "North Full", "north-full-payment")
    student = create_student(db_session, "Full", "Pay", "PAY-STU-012")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-05",
        issued_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        due_date=date(2026, 5, 30),
        total_amount="30.00",
        status=InvoiceStatus.open,
    )
    first = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Charge A",
        amount=Decimal("10.00"),
        period="2026-05",
        debt_created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        due_date=date(2026, 5, 5),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    second = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Charge B",
        amount=Decimal("20.00"),
        period="2026-05",
        debt_created_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
        due_date=date(2026, 5, 6),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
    )
    persist_entities(db_session, first, second)

    create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=invoice.id,
            amount="50.00",
            paid_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
            method="cash",
        ),
    )
    assert get_entity_by_id(db_session, Charge, first.id).status == ChargeStatus.paid
    assert get_entity_by_id(db_session, Charge, second.id).status == ChargeStatus.paid


def test_create_payment_keeps_cutoff_charge_unpaid_and_creates_carry_credit(db_session):
    """
    Validate payment allocation keeps cutoff charge unpaid and creates carry credit.

    1. Seed open invoice with one unpaid charge amount 100.00.
    2. Create payment for 30.00 once.
    3. Validate source charge remains unpaid and invoice closes.
    4. Validate carry credit charge is created for unallocatable remainder.
    """
    school = create_school(db_session, "North Split", "north-split-payment")
    student = create_student(db_session, "Split", "Pay", "PAY-STU-010")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-05",
        issued_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        due_date=date(2026, 5, 31),
        total_amount="100.00",
        status=InvoiceStatus.open,
    )
    source = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Source debt",
        amount=Decimal("100.00"),
        period="2026-05",
        debt_created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        due_date=date(2026, 5, 10),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    persist_entity(db_session, source)

    create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=invoice.id,
            amount="30.00",
            paid_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
            method="transfer",
        ),
    )
    refreshed_source = get_entity_by_id(db_session, Charge, source.id)
    refreshed_invoice = get_entity_by_id(db_session, Invoice, invoice.id)
    carry_credits = list_negative_unpaid_carry_for_student(db_session, student_id=student.id)
    assert refreshed_source is not None and refreshed_source.status == ChargeStatus.unpaid
    assert refreshed_invoice is not None and refreshed_invoice.status == InvoiceStatus.closed
    assert len(carry_credits) == 1
    assert carry_credits[0].amount == Decimal("-30.00")


def test_create_payment_partial_flow_pays_full_lines_and_creates_carry_credit(db_session):
    """
    Validate partial allocation pays full line, keeps cutoff unpaid, and creates carry credit.

    1. Seed open invoice with two unpaid charges 20 and 40.
    2. Create payment amount 30 to partially cover invoice.
    3. Reload charges and carry credit from database.
    4. Validate first is paid, second unpaid, invoice closed, and carry exists.
    """
    school = create_school(db_session, "North Continue", "north-continue-payment")
    student = create_student(db_session, "Continue", "Pay", "PAY-STU-013")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-06",
        issued_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        due_date=date(2026, 6, 30),
        total_amount="60.00",
        status=InvoiceStatus.open,
    )
    first = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="First",
        amount=Decimal("20.00"),
        period="2026-06",
        debt_created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        due_date=date(2026, 6, 5),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    second = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Second",
        amount=Decimal("40.00"),
        period="2026-06",
        debt_created_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        due_date=date(2026, 6, 6),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
    )
    persist_entities(db_session, first, second)

    create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=invoice.id,
            amount="30.00",
            paid_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            method="transfer",
        ),
    )
    carry_credits = list_negative_unpaid_carry_for_student(db_session, student_id=student.id)
    refreshed_invoice = get_entity_by_id(db_session, Invoice, invoice.id)
    assert get_entity_by_id(db_session, Charge, first.id).status == ChargeStatus.paid
    assert get_entity_by_id(db_session, Charge, second.id).status == ChargeStatus.unpaid
    assert refreshed_invoice is not None and refreshed_invoice.status == InvoiceStatus.closed
    assert len(carry_credits) == 1
    assert carry_credits[0].amount == Decimal("-10.00")


def test_create_payment_marks_negative_charges_paid(db_session):
    """
    Validate allocation marks unpaid negative charges as paid.

    1. Seed open invoice with one unpaid negative charge.
    2. Create payment once for same invoice.
    3. Reload negative charge from database.
    4. Validate negative charge status is paid.
    """
    school = create_school(db_session, "North Negative", "north-negative-payment")
    student = create_student(db_session, "Negative", "Pay", "PAY-STU-014")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-07",
        issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        due_date=date(2026, 7, 30),
        total_amount="-5.00",
        status=InvoiceStatus.open,
    )
    negative = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Credit",
        amount=Decimal("-5.00"),
        period="2026-07",
        debt_created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        due_date=date(2026, 7, 5),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
    )
    persist_entity(db_session, negative)

    create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=invoice.id,
            amount="5.00",
            paid_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
            method="cash",
        ),
    )
    assert get_entity_by_id(db_session, Charge, negative.id).status == ChargeStatus.paid


def test_create_payment_partial_flow_hits_zero_remaining_break(db_session):
    """
    Validate partial allocation stops when remaining reaches zero at loop start.

    1. Seed open invoice with two unpaid charges amount 10 and 10.
    2. Create payment for 10 once.
    3. Reload charges from database.
    4. Validate first is paid, second remains unpaid, and invoice closes.
    """
    school = create_school(db_session, "North Zero", "north-zero-payment")
    student = create_student(db_session, "Zero", "Pay", "PAY-STU-015")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-08",
        issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        due_date=date(2026, 8, 30),
        total_amount="20.00",
        status=InvoiceStatus.open,
    )
    first = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="First ten",
        amount=Decimal("10.00"),
        period="2026-08",
        debt_created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        due_date=date(2026, 8, 5),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    second = Charge(
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        fee_definition_id=None,
        origin_charge_id=None,
        description="Second ten",
        amount=Decimal("10.00"),
        period="2026-08",
        debt_created_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        due_date=date(2026, 8, 6),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
    )
    persist_entities(db_session, first, second)

    create_payment(
        db_session,
        school_id=school.id,
        payload=PaymentCreate(
            student_id=student.id,
            invoice_id=invoice.id,
            amount="10.00",
            paid_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            method="transfer",
        ),
    )
    refreshed_invoice = get_entity_by_id(db_session, Invoice, invoice.id)
    carry_credits = list_negative_unpaid_carry_for_student(db_session, student_id=student.id)
    assert get_entity_by_id(db_session, Charge, first.id).status == ChargeStatus.paid
    assert get_entity_by_id(db_session, Charge, second.id).status == ChargeStatus.unpaid
    assert refreshed_invoice is not None and refreshed_invoice.status == InvoiceStatus.closed
    assert carry_credits == []


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
        invoice_id=None,
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
    rows = list_from_query(db_session, query)
    payload = serialize_payment_response(rows[0])
    assert payload["student"]["id"] == student.id
    assert payload["invoice"]["id"] == invoice.id
    assert payload["method"] == "card"
