from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain.charge_enums import ChargeStatus, ChargeType
from tests.end2end.helpers_tc import setup_tc_context
from tests.helpers.factories import create_charge, list_interest_charges_for_origin


def test_tc_08_interest_delta_on_second_generation(client, db_session, seeded_users):
    """
    Validate TC-08 second generation creates only delta interest.

    1. Seed overdue fee 60 days and pre-existing interest equivalent to day-30 accrual.
    2. Trigger invoice generation through API.
    3. Validate a new interest charge is created.
    4. Validate new interest equals accrued delta only.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="08")
    today = datetime.now(timezone.utc).date()
    fee = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-08 fee",
        amount="100.00",
        due_date=today - timedelta(days=60),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        period="2026-01",
    )
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-08 existing interest",
        amount="2.00",
        due_date=today - timedelta(days=30),
        charge_type=ChargeType.interest,
        status=ChargeStatus.unpaid,
        period="2026-02",
        origin_charge_id=fee.id,
    )
    response = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert response.status_code == 201
    interests = list_interest_charges_for_origin(db_session, origin_charge_id=fee.id)
    assert len(interests) == 2
    latest = sorted(interests, key=lambda row: row.id)[-1]
    assert latest.amount == Decimal("2.00")
