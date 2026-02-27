from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.infrastructure.db.models import Charge
from tests.end2end.helpers_tc import setup_tc_context
from tests.helpers.factories import create_charge


def test_tc_09_no_interest_on_interest_charges(client, db_session, seeded_users):
    """
    Validate TC-09 no interest accrues on overdue interest charges.

    1. Seed one overdue unpaid interest charge.
    2. Trigger invoice generation through API.
    3. Query interest charges after generation.
    4. Validate no new interest charge was created from interest.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="09")
    today = datetime.now(timezone.utc).date()
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-09 interest only",
        amount="10.00",
        due_date=today - timedelta(days=45),
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
