from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.application.errors import NotFoundError
from app.application.services.charge_service import (
    create_charge,
    delete_charge,
    get_charge_by_id,
    get_fee_definition_in_school,
    get_student_in_school,
    get_unpaid_charges_for_student,
    serialize_charge_response,
    update_charge,
)
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.fee_recurrence import FeeRecurrence
from app.infrastructure.db.models import FeeDefinition
from app.interfaces.api.v1.schemas.charge import ChargeCreate, ChargeUpdate
from tests.helpers.factories import create_charge as factory_create_charge
from tests.helpers.factories import create_school, create_student, link_student_school


def test_get_student_in_school_returns_student_for_valid_link(db_session):
    """
    Validate get_student_in_school success behavior.

    1. Seed school and student with association link.
    2. Call get_student_in_school once.
    3. Validate helper returns a student object.
    4. Validate returned id matches seeded student.
    """
    school = create_school(db_session, "North", "north")
    student = create_student(db_session, "Alice", "Kid", "CHG-STU-001")
    link_student_school(db_session, student.id, school.id)
    found = get_student_in_school(db_session, student.id, school.id)
    assert found.id == student.id


def test_get_student_in_school_raises_not_found_for_missing_link(db_session):
    """
    Validate get_student_in_school missing-link branch.

    1. Seed school and student without association link.
    2. Call get_student_in_school once.
    3. Validate helper raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "North Missing", "north-missing")
    student = create_student(db_session, "Bob", "Kid", "CHG-STU-002")
    with pytest.raises(NotFoundError) as exc:
        get_student_in_school(db_session, student.id, school.id)
    assert str(exc.value) == "Student not found"


def test_get_fee_definition_in_school_raises_not_found_for_missing_fee(db_session):
    """
    Validate get_fee_definition_in_school missing fee branch.

    1. Seed one school without fee definitions.
    2. Call get_fee_definition_in_school once with unknown id.
    3. Validate helper raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "North Fees Missing", "north-fees-missing")
    with pytest.raises(NotFoundError) as exc:
        get_fee_definition_in_school(db_session, 999999, school.id)
    assert str(exc.value) == "Fee definition not found"


def test_create_charge_persists_charge_without_fee_definition(db_session):
    """
    Validate create_charge success without fee definition.

    1. Seed school and linked student for active tenant.
    2. Call create_charge with nullable fee_definition_id.
    3. Validate created charge fields are persisted.
    4. Validate status defaults from payload.
    """
    school = create_school(db_session, "Charge North", "charge-north")
    student = create_student(db_session, "Create", "Charge", "CHG-STU-003")
    link_student_school(db_session, student.id, school.id)
    created = create_charge(
        db_session,
        school.id,
        ChargeCreate(
            student_id=student.id,
            fee_definition_id=None,
            description="Manual adjustment",
            amount=Decimal("12.50"),
            period=None,
            debt_created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            due_date=date(2026, 3, 20),
            charge_type=ChargeType.penalty,
            status=ChargeStatus.unpaid,
        ),
    )
    assert created.description == "Manual adjustment"
    assert created.fee_definition_id is None
    assert created.charge_type == ChargeType.penalty
    assert created.status == ChargeStatus.unpaid


def test_create_charge_raises_not_found_for_missing_student(db_session):
    """
    Validate create_charge missing student branch.

    1. Seed one school without linked target student.
    2. Call create_charge using unknown student id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "Charge Missing Student", "charge-missing-student")
    with pytest.raises(NotFoundError) as exc:
        create_charge(
            db_session,
            school.id,
            ChargeCreate(
                student_id=999999,
                fee_definition_id=None,
                description="Invalid student",
                amount=Decimal("10.00"),
                period=None,
                debt_created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                due_date=date(2026, 4, 1),
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            ),
        )
    assert str(exc.value) == "Student not found"


def test_create_charge_raises_not_found_for_missing_fee_definition(db_session):
    """
    Validate create_charge missing fee definition branch.

    1. Seed school and linked student.
    2. Call create_charge with unknown fee_definition_id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "Charge Missing Fee", "charge-missing-fee")
    student = create_student(db_session, "Fee", "Missing", "CHG-STU-004")
    link_student_school(db_session, student.id, school.id)
    with pytest.raises(NotFoundError) as exc:
        create_charge(
            db_session,
            school.id,
            ChargeCreate(
                student_id=student.id,
                fee_definition_id=999999,
                description="Unknown fee",
                amount=Decimal("22.00"),
                period=None,
                debt_created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                due_date=date(2026, 4, 3),
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            ),
        )
    assert str(exc.value) == "Fee definition not found"


def test_get_charge_by_id_returns_none_for_other_school(db_session):
    """
    Validate get_charge_by_id tenant isolation behavior.

    1. Seed two schools and one charge in first school.
    2. Call get_charge_by_id from second school context.
    3. Validate helper returns no entity.
    4. Validate cross-tenant access is blocked.
    """
    school_a = create_school(db_session, "Charge School A", "charge-school-a")
    school_b = create_school(db_session, "Charge School B", "charge-school-b")
    student = create_student(db_session, "Tenant", "Kid", "CHG-STU-005")
    link_student_school(db_session, student.id, school_a.id)
    charge = factory_create_charge(
        db_session,
        school_id=school_a.id,
        student_id=student.id,
        description="Tenant charge",
        amount="33.00",
        due_date=date(2026, 5, 1),
    )
    assert get_charge_by_id(db_session, charge.id, school_b.id) is None


def test_update_charge_updates_all_mutable_fields(db_session):
    """
    Validate update_charge mutable field updates.

    1. Seed school with linked student, fee, and charge.
    2. Call update_charge with changed mutable values.
    3. Validate updated scalar fields are persisted.
    4. Validate enum fields reflect new payload values.
    """
    school = create_school(db_session, "Charge Update", "charge-update")
    student = create_student(db_session, "Update", "Kid", "CHG-STU-006")
    link_student_school(db_session, student.id, school.id)
    fee = FeeDefinition(
        school_id=school.id,
        name="Monthly",
        amount=Decimal("100.00"),
        recurrence=FeeRecurrence.monthly,
        is_active=True,
    )
    db_session.add(fee)
    db_session.commit()
    db_session.refresh(fee)
    charge = factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Old description",
        amount="40.00",
        due_date=date(2026, 5, 10),
    )
    updated = update_charge(
        db_session,
        charge,
        ChargeUpdate(
            student_id=student.id,
            fee_definition_id=fee.id,
            description="New description",
            amount=Decimal("55.00"),
            period="2026-05",
            debt_created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            due_date=date(2026, 5, 20),
            charge_type=ChargeType.interest,
            status=ChargeStatus.paid,
        ),
    )
    assert updated.description == "New description"
    assert updated.amount == Decimal("55.00")
    assert updated.period == "2026-05"
    assert updated.due_date == date(2026, 5, 20)
    assert updated.charge_type == ChargeType.interest
    assert updated.status == ChargeStatus.paid


def test_update_charge_raises_not_found_for_invalid_fee_definition(db_session):
    """
    Validate update_charge invalid fee definition branch.

    1. Seed school, student link, and one charge.
    2. Call update_charge with unknown fee_definition_id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "Charge Update Missing Fee", "charge-update-missing-fee")
    student = create_student(db_session, "Invalid", "Fee", "CHG-STU-007")
    link_student_school(db_session, student.id, school.id)
    charge = factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Base charge",
        amount="20.00",
        due_date=date(2026, 6, 1),
    )
    with pytest.raises(NotFoundError) as exc:
        update_charge(db_session, charge, ChargeUpdate(fee_definition_id=999999))
    assert str(exc.value) == "Fee definition not found"


def test_update_charge_allows_moving_charge_to_another_student_in_same_school(db_session):
    """
    Validate update_charge branch when target student changes.

    1. Seed school with two linked students and one charge for first student.
    2. Call update_charge with second student id once.
    3. Reload updated charge from database.
    4. Validate student_id now points to second student.
    """

    school = create_school(db_session, "Charge Move", "charge-move")
    first_student = create_student(db_session, "Move", "From", "CHG-STU-011")
    second_student = create_student(db_session, "Move", "To", "CHG-STU-012")
    link_student_school(db_session, first_student.id, school.id)
    link_student_school(db_session, second_student.id, school.id)
    charge = factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=first_student.id,
        description="Move charge",
        amount="18.00",
        due_date=date(2026, 7, 10),
    )
    updated = update_charge(db_session, charge, ChargeUpdate(student_id=second_student.id))
    assert updated.student_id == second_student.id


def test_delete_charge_sets_soft_delete_and_cancelled_status(db_session):
    """
    Validate delete_charge soft-delete behavior.

    1. Seed school, student link, and one charge.
    2. Call delete_charge once.
    3. Validate deleted_at timestamp is set.
    4. Validate status is forced to cancelled.
    """
    school = create_school(db_session, "Charge Delete", "charge-delete")
    student = create_student(db_session, "Delete", "Kid", "CHG-STU-008")
    link_student_school(db_session, student.id, school.id)
    charge = factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Delete charge",
        amount="12.00",
        due_date=date(2026, 6, 2),
    )
    delete_charge(db_session, charge)
    assert charge.deleted_at is not None
    assert charge.status == ChargeStatus.cancelled


def test_get_unpaid_charges_for_student_returns_items_and_total(db_session):
    """
    Validate get_unpaid_charges_for_student total calculation.

    1. Seed school, student, and mixed-status charges.
    2. Call get_unpaid_charges_for_student once.
    3. Validate only unpaid charges are included.
    4. Validate total unpaid matches sum of included charges.
    """
    school = create_school(db_session, "Charge Totals", "charge-totals")
    student = create_student(db_session, "Total", "Kid", "CHG-STU-009")
    link_student_school(db_session, student.id, school.id)
    factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Unpaid A",
        amount="10.00",
        due_date=date(2026, 7, 1),
        status=ChargeStatus.unpaid,
    )
    factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Paid B",
        amount="20.00",
        due_date=date(2026, 7, 2),
        status=ChargeStatus.paid,
    )
    factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Unpaid C",
        amount="5.50",
        due_date=date(2026, 7, 3),
        status=ChargeStatus.unpaid,
    )
    charges, total = get_unpaid_charges_for_student(db_session, school.id, student.id)
    assert len(charges) == 2
    assert total == Decimal("15.50")


def test_serialize_charge_response_includes_student_reference(db_session):
    """
    Validate serialize_charge_response nested student payload.

    1. Seed school, student link, and one charge.
    2. Call serialize_charge_response once.
    3. Validate payload contains student object fields.
    4. Validate charge metadata fields are included.
    """
    school = create_school(db_session, "Charge Serialize", "charge-serialize")
    student = create_student(db_session, "Serialize", "Kid", "CHG-STU-010")
    link_student_school(db_session, student.id, school.id)
    charge = factory_create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Serialize charge",
        amount="14.00",
        due_date=date(2026, 7, 4),
    )
    payload = serialize_charge_response(charge)
    assert payload["student"]["id"] == student.id
    assert payload["student"]["first_name"] == "Serialize"
    assert payload["description"] == "Serialize charge"
    assert payload["school_id"] == school.id
