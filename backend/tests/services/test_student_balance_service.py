from datetime import datetime, timezone
from decimal import Decimal

from app.application.services.student_balance_service import (
    get_student_balance_snapshot,
    invalidate_student_balance_cache,
    student_balance_cache_key,
)
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.infrastructure.db.models import Charge
from tests.helpers.factories import create_school, create_student, create_payment, link_student_school, persist_entities


def test_get_student_balance_snapshot_reads_from_cache_when_present(db_session, monkeypatch):
    """
    Validate student balance snapshot returns cached payload when available.

    1. Seed no financial rows and prepare mocked cache hit payload.
    2. Call balance snapshot helper once.
    3. Validate returned decimals match cached values.
    4. Validate database branch is bypassed by cache hit.
    """

    monkeypatch.setattr(
        "app.application.services.student_balance_service.get_json",
        lambda _key: {
            "total_charged_amount": "200.00",
            "total_paid_amount": "50.00",
            "total_unpaid_amount": "150.00",
            "total_unpaid_debt_amount": "155.00",
            "total_unpaid_credit_amount": "5.00",
        },
    )
    snapshot = get_student_balance_snapshot(db_session, school_id=1, student_id=1)
    assert snapshot["total_charged_amount"] == Decimal("200.00")
    assert snapshot["total_paid_amount"] == Decimal("50.00")
    assert snapshot["total_unpaid_amount"] == Decimal("150.00")
    assert snapshot["total_unpaid_debt_amount"] == Decimal("155.00")
    assert snapshot["total_unpaid_credit_amount"] == Decimal("5.00")


def test_get_student_balance_snapshot_computes_and_caches_when_missing(db_session, monkeypatch):
    """
    Validate student balance snapshot computes totals and writes cache on miss.

    1. Seed school, student, one positive unpaid charge, one negative unpaid charge, and payment.
    2. Mock cache miss and capture cache write payload.
    3. Call balance snapshot helper once.
    4. Validate computed totals and cache write values.
    """

    school = create_school(db_session, "Cache School", "cache-school")
    student = create_student(db_session, "Cache", "Kid", "CACHE-STU-001")
    link_student_school(db_session, student.id, school.id)
    persist_entities(
        db_session,
        Charge(
            school_id=school.id,
            student_id=student.id,
            invoice_id=None,
            fee_definition_id=None,
            origin_charge_id=None,
            description="Main debt",
            amount=Decimal("120.00"),
            period="2026-01",
            debt_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            due_date=datetime(2026, 1, 10, tzinfo=timezone.utc).date(),
            charge_type=ChargeType.fee,
            status=ChargeStatus.unpaid,
        ),
        Charge(
            school_id=school.id,
            student_id=student.id,
            invoice_id=None,
            fee_definition_id=None,
            origin_charge_id=None,
            description="Credit",
            amount=Decimal("-20.00"),
            period="2026-01",
            debt_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            due_date=datetime(2026, 1, 10, tzinfo=timezone.utc).date(),
            charge_type=ChargeType.penalty,
            status=ChargeStatus.unpaid,
        ),
    )
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        amount="30.00",
        paid_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )

    captured = {"key": None, "value": None, "ttl": None}
    monkeypatch.setattr("app.application.services.student_balance_service.get_json", lambda _key: None)

    def _capture_set_json(cache_key, value, ttl_seconds):
        captured["key"] = cache_key
        captured["value"] = value
        captured["ttl"] = ttl_seconds

    monkeypatch.setattr("app.application.services.student_balance_service.set_json", _capture_set_json)
    snapshot = get_student_balance_snapshot(db_session, school_id=school.id, student_id=student.id)
    assert snapshot["total_charged_amount"] == Decimal("120.00")
    assert snapshot["total_paid_amount"] == Decimal("30.00")
    assert snapshot["total_unpaid_amount"] == Decimal("100.00")
    assert snapshot["total_unpaid_debt_amount"] == Decimal("120.00")
    assert snapshot["total_unpaid_credit_amount"] == Decimal("20.00")
    assert captured["key"] == student_balance_cache_key(school_id=school.id, student_id=student.id)
    assert captured["value"]["total_unpaid_amount"] == "100.00"


def test_invalidate_student_balance_cache_deletes_expected_key(monkeypatch):
    """
    Validate student balance cache invalidation deletes the scoped key.

    1. Mock cache delete and capture target key.
    2. Call invalidate helper once.
    3. Validate generated key includes school and student ids.
    4. Validate delete operation is executed exactly for that key.
    """

    deleted = {"key": None}
    monkeypatch.setattr("app.application.services.student_balance_service.delete_key", lambda key: deleted.update(key=key))
    invalidate_student_balance_cache(school_id=9, student_id=77)
    assert deleted["key"] == "student_balance:9:77"
