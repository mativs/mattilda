from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.infrastructure.db.models import Charge
from tests.end2end.helpers_tc import setup_tc_context
from tests.helpers.factories import create_charge


def test_tc_07_overdue_fee_generates_interest(client, db_session, seeded_users):
    """
    Validate TC-07 overdue fee generates expected interest at 2% monthly.

    1. Seed overdue fee 100 unpaid by 30 days.
    2. Trigger invoice generation through API.
    3. Validate one interest charge is created.
    4. Validate interest amount and origin_charge_id are correct.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="07")
    today = datetime.now(timezone.utc).date()
    base = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-07 fee",
        amount="100.00",
        due_date=today - timedelta(days=30),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        period="2026-01",
    )
    response = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert response.status_code == 201
    interests = list(
        db_session.execute(
            select(Charge).where(
                Charge.student_id == student.id,
                Charge.origin_charge_id == base.id,
                Charge.charge_type == ChargeType.interest,
            )
        )
        .scalars()
        .all()
    )
    assert len(interests) == 1
    # 2% monthly with 30-day divisor and exactly 30 days overdue.
    assert interests[0].amount == Decimal("2.00")
