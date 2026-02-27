from datetime import date

from app.domain.charge_enums import ChargeType
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context


def test_tc_13_overdue_invoice_receives_payment(client, db_session, seeded_users):
    """
    Validate TC-13 overdue invoice payment is rejected.

    1. Seed open invoice with one unpaid fee.
    2. Create payment with paid_at after due_date.
    3. Validate API rejects request.
    4. Validate status code is 400.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="13")
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-09",
        due_date=date(2026, 9, 10),
        charges=[("TC-13 fee", "100.00", ChargeType.fee, date(2026, 9, 1))],
    )
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "20.00",
            "paid_at": "2030-01-01T10:00:00Z",
            "method": "cash",
        },
    )
    assert response.status_code == 400
