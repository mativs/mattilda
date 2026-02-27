from datetime import date
from decimal import Decimal

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context


def test_tc_04_simple_partial_payment(client, db_session, seeded_users):
    """
    Validate TC-04 simple partial payment.

    1. Seed one fee 100 in an open invoice.
    2. Create payment of 60 through API.
    3. Validate source charge is paid and residual 40 is created.
    4. Validate invoice remains open.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="04")
    invoice, charges = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-04",
        due_date=date(2026, 4, 30),
        charges=[("TC-04 fee", "100.00", ChargeType.fee, date(2026, 4, 1))],
    )
    source_charge_id = charges[0].id
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "60.00",
            "paid_at": "2026-04-15T10:00:00Z",
            "method": "transfer",
        },
    )
    assert response.status_code == 201
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.open
    all_charges = list(student.charges)
    source = next(charge for charge in all_charges if charge.id == source_charge_id)
    residual = next(charge for charge in all_charges if charge.origin_charge_id == source_charge_id)
    assert source.status == ChargeStatus.paid
    assert residual.status == ChargeStatus.unpaid
    assert residual.amount == Decimal("40.00")
