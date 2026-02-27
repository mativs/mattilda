from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.application.errors import ValidationError
from app.application.services.invoice_generation_service import generate_invoice_for_student
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge, Invoice
from tests.helpers.factories import (
    create_charge,
    create_invoice,
    create_school,
    create_student,
    get_entity_by_id,
    list_interest_charges_for_origin,
    list_interest_charges_for_student,
    link_student_school,
    persist_entity,
)


def test_generate_invoice_closes_existing_open_and_creates_new_invoice(db_session):
    """
    Validate invoice generation closes previous open invoice and creates a new one.

    1. Seed student with one open invoice and one unpaid charge.
    2. Call generate_invoice_for_student once.
    3. Validate old open invoice is now closed.
    4. Validate new invoice is open and contains generated items.
    """
    school = create_school(db_session, "North Gen", "north-gen")
    student = create_student(db_session, "Gen", "Student", "INV-GEN-001")
    link_student_school(db_session, student.id, school.id)
    previous_open = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        total_amount="50.00",
        status=InvoiceStatus.open,
    )
    persist_entity(
        db_session,
        Charge(
            school_id=school.id,
            student_id=student.id,
            invoice_id=None,
            fee_definition_id=None,
            origin_charge_id=None,
            description="Base unpaid",
            amount=Decimal("75.00"),
            period="2026-04",
            debt_created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            due_date=date(2026, 4, 15),
            charge_type=ChargeType.fee,
            status=ChargeStatus.unpaid,
        ),
    )

    generated = generate_invoice_for_student(
        db=db_session,
        school_id=school.id,
        student_id=student.id,
        as_of=date(2026, 4, 20),
    )
    old = get_entity_by_id(db_session, Invoice, previous_open.id)
    assert old is not None and old.status == InvoiceStatus.closed
    assert generated.status == InvoiceStatus.open
    assert generated.total_amount == Decimal("75.25")


def test_generate_invoice_creates_interest_delta_for_overdue_fee_only(db_session):
    """
    Validate invoice generation creates only delta interest for overdue fee charges.

    1. Seed overdue fee charge and one existing unpaid interest charge.
    2. Call generate_invoice_for_student once with later as-of date.
    3. Validate one extra interest charge is created for positive delta.
    4. Validate generated interest links to origin charge id.
    """
    school = create_school(db_session, "North Int", "north-int")
    student = create_student(db_session, "Interest", "Student", "INV-GEN-002")
    link_student_school(db_session, student.id, school.id)
    base = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Monthly fee",
        amount="100.00",
        due_date=date(2026, 1, 10),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        period="2026-01",
        debt_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Existing interest",
        amount="2.00",
        due_date=date(2026, 2, 1),
        charge_type=ChargeType.interest,
        status=ChargeStatus.unpaid,
        period="2026-01",
        debt_created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        origin_charge_id=base.id,
    )

    generate_invoice_for_student(
        db=db_session,
        school_id=school.id,
        student_id=student.id,
        as_of=date(2026, 3, 11),
    )
    interests = list_interest_charges_for_origin(db_session, origin_charge_id=base.id)
    assert len(interests) >= 2
    assert sum((charge.amount for charge in interests), Decimal("0.00")) > Decimal("2.00")


def test_generate_invoice_raises_validation_without_unpaid_charges(db_session):
    """
    Validate invoice generation rejects when there are no unpaid charges.

    1. Seed school and linked student without unpaid charges.
    2. Call generate_invoice_for_student once.
    3. Validate service raises ValidationError.
    4. Validate message explains missing unpaid charges.
    """
    school = create_school(db_session, "North Empty", "north-empty")
    student = create_student(db_session, "Empty", "Student", "INV-GEN-003")
    link_student_school(db_session, student.id, school.id)
    with pytest.raises(ValidationError) as exc:
        generate_invoice_for_student(db=db_session, school_id=school.id, student_id=student.id, as_of=date(2026, 3, 1))
    assert str(exc.value) == "No unpaid charges available for invoice generation"


def test_generate_invoice_skips_interest_for_non_overdue_fee(db_session):
    """
    Validate invoice generation does not create interest for non-overdue fees.

    1. Seed one unpaid fee charge with due date equal to as-of date.
    2. Call generate_invoice_for_student once.
    3. Query interest charges for same student.
    4. Validate no interest charges were generated.
    """
    school = create_school(db_session, "North No Int", "north-no-int")
    student = create_student(db_session, "No", "Interest", "INV-GEN-004")
    link_student_school(db_session, student.id, school.id)
    persist_entity(
        db_session,
        Charge(
            school_id=school.id,
            student_id=student.id,
            invoice_id=None,
            fee_definition_id=None,
            origin_charge_id=None,
            description="On-time fee",
            amount=Decimal("100.00"),
            period="2026-06",
            debt_created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            due_date=date(2026, 6, 10),
            charge_type=ChargeType.fee,
            status=ChargeStatus.unpaid,
        ),
    )

    generate_invoice_for_student(db=db_session, school_id=school.id, student_id=student.id, as_of=date(2026, 6, 10))
    interests = list_interest_charges_for_student(db_session, student_id=student.id)
    assert len(interests) == 0


def test_generate_invoice_skips_interest_when_delta_is_not_positive(db_session):
    """
    Validate invoice generation skips interest creation when accrued delta is not positive.

    1. Seed overdue fee and existing unpaid interest greater than accrued amount.
    2. Call generate_invoice_for_student once.
    3. Query interest charges linked to base fee.
    4. Validate no additional interest charge was added.
    """
    school = create_school(db_session, "North Delta", "north-delta")
    student = create_student(db_session, "Delta", "Student", "INV-GEN-005")
    link_student_school(db_session, student.id, school.id)
    base = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Base overdue fee",
        amount="100.00",
        due_date=date(2026, 1, 10),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        period="2026-01",
        debt_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Pre-existing high interest",
        amount="50.00",
        due_date=date(2026, 2, 1),
        charge_type=ChargeType.interest,
        status=ChargeStatus.unpaid,
        period="2026-01",
        debt_created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        origin_charge_id=base.id,
    )

    generate_invoice_for_student(db=db_session, school_id=school.id, student_id=student.id, as_of=date(2026, 3, 11))
    interests = list_interest_charges_for_origin(db_session, origin_charge_id=base.id)
    assert len(interests) == 1
