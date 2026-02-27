from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.infrastructure.db.models import Charge
from tests.end2end.helpers_tc import setup_tc_context
from tests.helpers.factories import create_charge


def test_tc_10_paid_fee_unpaid_interest_no_compound(client, db_session, seeded_users):
    """
    Validate TC-10 paid fee with unpaid interest does not compound interest.

    1. Seed one paid fee and one unpaid overdue interest charge.
    2. Trigger invoice generation through API.
    3. Query interest charges for the student.
    4. Validate no additional interest charge is generated.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="10")
    today = datetime.now(timezone.utc).date()
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-10 fee paid",
        amount="100.00",
        due_date=today - timedelta(days=40),
        charge_type=ChargeType.fee,
        status=ChargeStatus.paid,
        period="2026-01",
    )
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-10 interest unpaid",
        amount="10.00",
        due_date=today - timedelta(days=30),
        charge_type=ChargeType.interest,
        status=ChargeStatus.unpaid,
        period="2026-01",
    )
    response = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert response.status_code == 201
    interests = list(
        db_session.execute(
            select(Charge).where(Charge.student_id == student.id, Charge.charge_type == ChargeType.interest)
        )
        .scalars()
        .all()
    )
    assert len(interests) == 1
