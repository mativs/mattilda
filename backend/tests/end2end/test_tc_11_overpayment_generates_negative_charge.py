from datetime import date
from decimal import Decimal

from app.domain.charge_enums import ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context
from tests.helpers.factories import list_negative_unpaid_carry_for_student, refresh_entity


def test_tc_11_overpayment_generates_negative_charge(client, db_session, seeded_users):
    """
    Validate TC-11 overpayment creates negative carry charge.

    1. Seed open invoice with one unpaid charge of 100.
    2. Create payment of 120 through API.
    3. Validate invoice closes and source charge is paid.
    4. Validate one negative carry charge of 20 is created.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="11")
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-11",
        due_date=date(2026, 11, 30),
        charges=[("TC-11 fee", "100.00", ChargeType.fee, date(2026, 11, 1))],
    )
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "120.00",
            "paid_at": "2026-11-20T10:00:00Z",
            "method": "transfer",
        },
    )
    assert response.status_code == 201
    refresh_entity(db_session, invoice)
    assert invoice.status == InvoiceStatus.closed
    negative = list_negative_unpaid_carry_for_student(db_session, student_id=student.id)
    assert len(negative) == 1
    assert negative[0].amount == Decimal("-20.00")
