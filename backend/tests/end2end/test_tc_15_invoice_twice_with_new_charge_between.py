from datetime import datetime, timezone

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Invoice, InvoiceItem
from tests.end2end.helpers_tc import setup_tc_context
from tests.helpers.factories import create_charge


def test_tc_15_invoice_generated_twice_with_charge_between(client, db_session, seeded_users):
    """
    Validate TC-15 second generation includes newly added charge.

    1. Seed one unpaid charge and generate first invoice.
    2. Add another unpaid charge and generate invoice again.
    3. Validate first invoice is closed and second is open.
    4. Validate second invoice has previous plus new charge items.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="15")
    today = datetime.now(timezone.utc).date()
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-15 charge A",
        amount="100.00",
        due_date=today,
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        period=f"{today.year:04d}-{today.month:02d}",
    )
    first = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert first.status_code == 201
    first_id = first.json()["id"]

    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-15 charge B",
        amount="50.00",
        due_date=today,
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
        period=f"{today.year:04d}-{today.month:02d}",
    )
    second = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert second_id != first_id

    inv1 = db_session.get(Invoice, first_id)
    inv2 = db_session.get(Invoice, second_id)
    assert inv1 is not None and inv1.status == InvoiceStatus.closed
    assert inv2 is not None and inv2.status == InvoiceStatus.open
    items2 = list(db_session.execute(select(InvoiceItem).where(InvoiceItem.invoice_id == second_id)).scalars().all())
    assert len(items2) == 2
