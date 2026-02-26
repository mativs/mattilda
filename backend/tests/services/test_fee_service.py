from decimal import Decimal

import pytest

from app.application.errors import ConflictError
from app.application.services.fee_service import (
    create_fee_definition,
    delete_fee_definition,
    get_fee_definition_by_id,
    serialize_fee_response,
    update_fee_definition,
)
from app.domain.fee_recurrence import FeeRecurrence
from app.infrastructure.db.models import FeeDefinition
from app.interfaces.api.v1.schemas.fee import FeeCreate, FeeUpdate
from tests.helpers.factories import create_school


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


def test_create_fee_definition_persists_new_fee(db_session):
    """
    Validate create_fee_definition success behavior.

    1. Seed one active school for tenancy scope.
    2. Call create_fee_definition once.
    3. Validate fee name and recurrence are persisted.
    4. Validate amount and active state are persisted.
    """
    school = create_school(db_session, "North Fees", "north-fees")
    fee = create_fee_definition(
        db_session,
        school.id,
        FeeCreate(name="Cuota mensual", amount=Decimal("150.00"), recurrence=FeeRecurrence.monthly, is_active=True),
    )
    assert fee.name == "Cuota mensual"
    assert fee.recurrence == FeeRecurrence.monthly
    assert fee.amount == Decimal("150.00")
    assert fee.is_active is True


def test_create_fee_definition_raises_conflict_for_duplicate_natural_key(db_session):
    """
    Validate create_fee_definition duplicate natural-key conflict.

    1. Seed one school and one existing fee definition.
    2. Call create_fee_definition with same name and recurrence.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    school = create_school(db_session, "Duplicate Fees", "duplicate-fees")
    _create_fee(db_session, school.id, "Matrícula", "450.00", FeeRecurrence.annual)
    with pytest.raises(ConflictError) as exc:
        create_fee_definition(
            db_session,
            school.id,
            FeeCreate(name="Matrícula", amount=Decimal("400.00"), recurrence=FeeRecurrence.annual, is_active=True),
        )
    assert str(exc.value) == "Fee definition already exists"


def test_get_fee_definition_by_id_returns_fee_for_same_school(db_session):
    """
    Validate get_fee_definition_by_id school-scoped success.

    1. Seed school and one fee record.
    2. Call get_fee_definition_by_id with same school context.
    3. Validate function returns an entity.
    4. Validate returned id matches seeded fee id.
    """
    school = create_school(db_session, "Scoped Fees", "scoped-fees")
    fee = _create_fee(db_session, school.id, "Materiales", "90.00", FeeRecurrence.one_time)
    found = get_fee_definition_by_id(db_session, fee.id, school.id)
    assert found is not None
    assert found.id == fee.id


def test_get_fee_definition_by_id_returns_none_for_other_school(db_session):
    """
    Validate get_fee_definition_by_id tenant isolation behavior.

    1. Seed two schools and one fee on first school.
    2. Call get_fee_definition_by_id from second school context.
    3. Validate result is None.
    4. Validate cross-tenant visibility is blocked.
    """
    school_a = create_school(db_session, "School A Fees", "school-a-fees")
    school_b = create_school(db_session, "School B Fees", "school-b-fees")
    fee = _create_fee(db_session, school_a.id, "Annual Fee", "300.00", FeeRecurrence.annual)
    assert get_fee_definition_by_id(db_session, fee.id, school_b.id) is None


def test_serialize_fee_response_includes_expected_fields(db_session):
    """
    Validate serialize_fee_response payload shape.

    1. Seed school and fee entity.
    2. Call serialize_fee_response once.
    3. Validate primary scalar fields in payload.
    4. Validate school_id and recurrence are included.
    """
    school = create_school(db_session, "Serialize Fees", "serialize-fees")
    fee = _create_fee(db_session, school.id, "Libros", "50.00", FeeRecurrence.one_time)
    payload = serialize_fee_response(fee)
    assert payload["id"] == fee.id
    assert payload["school_id"] == school.id
    assert payload["name"] == "Libros"
    assert payload["recurrence"] == FeeRecurrence.one_time


def test_update_fee_definition_updates_mutable_fields(db_session):
    """
    Validate update_fee_definition field update behavior.

    1. Seed school and one fee record.
    2. Call update_fee_definition with new values.
    3. Validate name, amount, recurrence were changed.
    4. Validate active flag reflects payload.
    """
    school = create_school(db_session, "Update Fees", "update-fees")
    fee = _create_fee(db_session, school.id, "Old Name", "100.00", FeeRecurrence.monthly)
    updated = update_fee_definition(
        db_session,
        fee,
        FeeUpdate(name="New Name", amount=Decimal("125.00"), recurrence=FeeRecurrence.annual, is_active=False),
    )
    assert updated.name == "New Name"
    assert updated.amount == Decimal("125.00")
    assert updated.recurrence == FeeRecurrence.annual
    assert updated.is_active is False


def test_update_fee_definition_raises_conflict_when_target_natural_key_exists(db_session):
    """
    Validate update_fee_definition duplicate natural-key conflict.

    1. Seed school with two different fee definitions.
    2. Call update_fee_definition moving first fee to second key.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    school = create_school(db_session, "Update Conflict Fees", "update-conflict-fees")
    fee_a = _create_fee(db_session, school.id, "Fee A", "100.00", FeeRecurrence.monthly)
    _create_fee(db_session, school.id, "Fee B", "200.00", FeeRecurrence.annual)
    with pytest.raises(ConflictError) as exc:
        update_fee_definition(
            db_session,
            fee_a,
            FeeUpdate(name="Fee B", recurrence=FeeRecurrence.annual),
        )
    assert str(exc.value) == "Fee definition already exists"


def test_delete_fee_definition_sets_soft_delete_flags(db_session):
    """
    Validate delete_fee_definition soft-delete behavior.

    1. Seed school and fee record.
    2. Call delete_fee_definition once.
    3. Validate is_active is set to false.
    4. Validate deleted_at timestamp is populated.
    """
    school = create_school(db_session, "Delete Fees", "delete-fees")
    fee = _create_fee(db_session, school.id, "Delete Me", "80.00", FeeRecurrence.one_time)
    delete_fee_definition(db_session, fee)
    assert fee.is_active is False
    assert fee.deleted_at is not None
