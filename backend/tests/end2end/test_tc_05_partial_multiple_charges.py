from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context


def test_tc_05_partial_payment_multiple_charges(client, db_session, seeded_users):
    """
    Validate TC-05 partial payment across multiple charges.

    1. Seed charges 100, 50, 30 in one open invoice.
    2. Create payment of 120 through API.
    3. Validate two paid source charges and residual 30 from second charge.
    4. Validate invoice remains open.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="05")
    invoice, charges = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-05",
        due_date=date(2026, 5, 31),
        charges=[
            ("TC-05 charge A", "100.00", ChargeType.fee, date(2026, 5, 1)),
            ("TC-05 charge B", "50.00", ChargeType.fee, date(2026, 5, 2)),
            ("TC-05 charge C", "30.00", ChargeType.penalty, date(2026, 5, 3)),
        ],
    )
    second_id = charges[1].id
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "120.00",
            "paid_at": "2026-05-20T10:00:00Z",
            "method": "transfer",
        },
    )
    assert response.status_code == 201
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.open
    all_charges = list(db_session.execute(select(Charge).where(Charge.student_id == student.id)).scalars().all())
    residual = next(charge for charge in all_charges if charge.origin_charge_id == second_id)
    source_by_id = {charge.id: charge for charge in all_charges if charge.id in [item.id for item in charges]}
    assert source_by_id[charges[0].id].status == ChargeStatus.paid
    assert source_by_id[charges[1].id].status == ChargeStatus.paid
    assert source_by_id[charges[2].id].status == ChargeStatus.unpaid
    assert residual.status == ChargeStatus.unpaid
    assert residual.amount == Decimal("30.00")
