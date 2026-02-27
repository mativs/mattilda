from datetime import date

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, get_invoice_charges, setup_tc_context


def test_tc_02_full_payment_multiple_charges(client, db_session, seeded_users):
    """
    Validate TC-02 full payment with two charges.

    1. Seed fee 100 and penalty 50 in one open invoice.
    2. Create payment of 150 through API.
    3. Validate both charges become paid.
    4. Validate invoice status becomes closed.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="02")
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-02",
        due_date=date(2026, 2, 28),
        charges=[
            ("TC-02 fee", "100.00", ChargeType.fee, date(2026, 2, 1)),
            ("TC-02 penalty", "50.00", ChargeType.penalty, date(2026, 2, 2)),
        ],
    )
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "150.00",
            "paid_at": "2026-02-20T10:00:00Z",
            "method": "cash",
        },
    )
    assert response.status_code == 201
    charges = get_invoice_charges(db_session, invoice_id=invoice.id)
    assert all(charge.status == ChargeStatus.paid for charge in charges if charge.amount > 0)
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.closed
