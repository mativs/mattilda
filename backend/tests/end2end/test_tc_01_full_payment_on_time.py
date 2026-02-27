from datetime import date

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, get_invoice_charges, setup_tc_context


def test_tc_01_full_payment_on_time(client, db_session, seeded_users):
    """
    Validate TC-01 full payment on time.

    1. Seed one fee charge of 100 with open invoice.
    2. Create payment of 100 before due date through API.
    3. Validate charge status becomes paid.
    4. Validate invoice status becomes closed.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="01")
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-01",
        due_date=date(2026, 1, 31),
        charges=[("TC-01 fee", "100.00", ChargeType.fee, date(2026, 1, 1))],
    )
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "100.00",
            "paid_at": "2026-01-20T10:00:00Z",
            "method": "transfer",
        },
    )
    assert response.status_code == 201
    charges = get_invoice_charges(db_session, invoice_id=invoice.id)
    assert charges[0].status == ChargeStatus.paid
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.closed
