from datetime import datetime, timezone

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge, Invoice, InvoiceItem
from tests.end2end.helpers_tc import setup_tc_context
from tests.helpers.factories import create_charge


def test_tc_14_invoice_generated_twice_same_period(client, db_session, seeded_users):
    """
    Validate TC-14 repeated generation in same period.

    1. Seed one unpaid fee charge for current period.
    2. Generate invoice twice via API.
    3. Validate first invoice is closed and second is open.
    4. Validate second invoice contains same item set.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="14")
    today = datetime.now(timezone.utc).date()
    create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-14 fee",
        amount="100.00",
        due_date=today,
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        period=f"{today.year:04d}-{today.month:02d}",
    )
    first = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert first.status_code == 201
    first_id = first.json()["id"]
    second = client.post(f"/api/v1/students/{student.id}/invoices/generate", headers=headers)
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert second_id != first_id

    inv1 = db_session.get(Invoice, first_id)
    inv2 = db_session.get(Invoice, second_id)
    assert inv1 is not None and inv1.status == InvoiceStatus.closed
    assert inv2 is not None and inv2.status == InvoiceStatus.open
    items1 = list(db_session.execute(select(InvoiceItem).where(InvoiceItem.invoice_id == first_id)).scalars().all())
    items2 = list(db_session.execute(select(InvoiceItem).where(InvoiceItem.invoice_id == second_id)).scalars().all())
    assert len(items1) == len(items2) == 1
    charges = list(db_session.execute(select(Charge).where(Charge.student_id == student.id)).scalars().all())
    assert all(charge.invoice_id == second_id for charge in charges if charge.status == ChargeStatus.unpaid)
