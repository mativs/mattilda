from datetime import date, datetime, timedelta, timezone

from app.application.services.reconciliation_checks_service import run_all_reconciliation_checks
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.helpers.factories import (
    create_charge,
    create_invoice,
    create_invoice_item,
    create_payment,
    create_school,
    create_student,
    link_student_school,
)


def test_reconciliation_detects_invoice_total_mismatch(db_session):
    """
    Validate check A detects invoice total mismatch against invoice items sum.

    1. Seed one invoice with total 100 and one item totaling 80.
    2. Run all reconciliation checks once.
    3. Read findings output.
    4. Validate invoice_total_mismatch finding exists.
    """

    school = create_school(db_session, "Recon A", "recon-a")
    student = create_student(db_session, "A", "Student", "REC-A-001")
    link_student_school(db_session, student.id, school.id)
    charge = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="A debt",
        amount="80.00",
        due_date=date(2026, 7, 10),
    )
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-07",
        issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        due_date=date(2026, 7, 10),
        total_amount="100.00",
        status=InvoiceStatus.open,
    )
    create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=charge.id,
        description="A item",
        amount="80.00",
    )

    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=datetime(2026, 7, 2, tzinfo=timezone.utc))
    assert any(item["check_code"] == "invoice_total_mismatch" and item["entity_id"] == invoice.id for item in findings)


def test_reconciliation_detects_orphan_unpaid_charge_with_open_not_due_invoice(db_session):
    """
    Validate check B detects orphan unpaid charges when student has open not-due invoice.

    1. Seed student with one open not-due invoice.
    2. Seed one overdue unpaid charge with no invoice linkage.
    3. Run all checks once with as_of date.
    4. Validate orphan_unpaid_charge finding exists.
    """

    school = create_school(db_session, "Recon B", "recon-b")
    student = create_student(db_session, "B", "Student", "REC-B-001")
    link_student_school(db_session, student.id, school.id)
    create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-08",
        issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        due_date=date(2026, 8, 31),
        total_amount="30.00",
        status=InvoiceStatus.open,
    )
    charge = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Orphan debt",
        amount="30.00",
        due_date=date(2026, 8, 1),
        status=ChargeStatus.unpaid,
        invoice_id=None,
    )
    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=datetime(2026, 8, 10, tzinfo=timezone.utc))
    assert any(item["check_code"] == "orphan_unpaid_charge" and item["entity_id"] == charge.id for item in findings)


def test_reconciliation_detects_invoice_item_cancelled_charge_without_residual(db_session):
    """
    Validate check C detects invoice items pointing to cancelled charge without residual.

    1. Seed one cancelled charge included in invoice item.
    2. Do not create residual charge.
    3. Run all checks once.
    4. Validate invoice_item_cancelled_charge_no_residual finding exists.
    """

    school = create_school(db_session, "Recon C", "recon-c")
    student = create_student(db_session, "C", "Student", "REC-C-001")
    link_student_school(db_session, student.id, school.id)
    charge = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Cancelled debt",
        amount="40.00",
        due_date=date(2026, 9, 10),
        status=ChargeStatus.cancelled,
    )
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-09",
        issued_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        due_date=date(2026, 9, 10),
        total_amount="40.00",
    )
    item = create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=charge.id,
        description="Cancelled item",
        amount="40.00",
    )
    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=datetime(2026, 9, 2, tzinfo=timezone.utc))
    assert any(
        item_payload["check_code"] == "invoice_item_cancelled_charge_no_residual" and item_payload["entity_id"] == item.id
        for item_payload in findings
    )


def test_reconciliation_detects_interest_invalid_origin(db_session):
    """
    Validate check D detects interest charges with missing origin reference.

    1. Seed one interest charge with null origin id.
    2. Run all checks once.
    3. Read findings output.
    4. Validate interest_invalid_origin finding exists.
    """

    school = create_school(db_session, "Recon D", "recon-d")
    student = create_student(db_session, "D", "Student", "REC-D-001")
    link_student_school(db_session, student.id, school.id)
    interest = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Interest without origin",
        amount="5.00",
        due_date=date(2026, 10, 10),
        charge_type=ChargeType.interest,
        origin_charge_id=None,
    )
    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=datetime(2026, 10, 2, tzinfo=timezone.utc))
    assert any(item["check_code"] == "interest_invalid_origin" and item["entity_id"] == interest.id for item in findings)


def test_reconciliation_detects_open_invoice_with_sufficient_payments(db_session):
    """
    Validate check E detects open invoices fully covered by confirmed payments.

    1. Seed open invoice with total 100.
    2. Seed confirmed payment amount 100 for same invoice.
    3. Run all checks once.
    4. Validate invoice_open_with_sufficient_payments finding exists.
    """

    school = create_school(db_session, "Recon E", "recon-e")
    student = create_student(db_session, "E", "Student", "REC-E-001")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-11",
        issued_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        due_date=date(2026, 11, 10),
        total_amount="100.00",
        status=InvoiceStatus.open,
    )
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        amount="100.00",
        paid_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
    )
    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert any(
        item["check_code"] == "invoice_open_with_sufficient_payments" and item["entity_id"] == invoice.id for item in findings
    )


def test_reconciliation_detects_unapplied_negative_charge(db_session):
    """
    Validate check F detects unpaid negative charge still linked to paid invoice flow.

    1. Seed open invoice with one confirmed payment.
    2. Seed negative unpaid charge linked to same invoice.
    3. Run all checks once.
    4. Validate unapplied_negative_charge finding exists.
    """

    school = create_school(db_session, "Recon F", "recon-f")
    student = create_student(db_session, "F", "Student", "REC-F-001")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-12",
        issued_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        due_date=date(2026, 12, 10),
        total_amount="20.00",
        status=InvoiceStatus.open,
    )
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        amount="10.00",
        paid_at=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    negative = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Credit",
        amount="-5.00",
        due_date=date(2026, 12, 2),
        status=ChargeStatus.unpaid,
        invoice_id=invoice.id,
        charge_type=ChargeType.penalty,
    )
    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=datetime(2026, 12, 3, tzinfo=timezone.utc))
    assert any(item["check_code"] == "unapplied_negative_charge" and item["entity_id"] == negative.id for item in findings)


def test_reconciliation_detects_duplicate_payments(db_session):
    """
    Validate check G detects duplicate payments in a narrow time window.

    1. Seed two payments with same student, amount, and close timestamps.
    2. Run all checks once.
    3. Read findings output.
    4. Validate duplicate_payment_window finding exists.
    """

    school = create_school(db_session, "Recon G", "recon-g")
    student = create_student(db_session, "G", "Student", "REC-G-001")
    link_student_school(db_session, student.id, school.id)
    base_time = datetime(2026, 12, 20, 10, 0, tzinfo=timezone.utc)
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        amount="25.00",
        paid_at=base_time,
    )
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        amount="25.00",
        paid_at=base_time + timedelta(seconds=30),
    )
    findings = run_all_reconciliation_checks(db_session, school_id=school.id, as_of=base_time + timedelta(minutes=1))
    assert any(item["check_code"] == "duplicate_payment_window" for item in findings)
