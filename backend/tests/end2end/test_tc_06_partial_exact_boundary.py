from datetime import date

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context


def test_tc_06_payment_exact_boundary(client, db_session, seeded_users):
    """
    Validate TC-06 payment exactly on charge boundary.

    1. Seed two charges of 100 each in open invoice.
    2. Create payment of 100 through API.
    3. Validate first charge is paid and second remains unpaid.
    4. Validate no residual or carry-credit charges are created and invoice closes.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="06")
    invoice, charges = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-06",
        due_date=date(2026, 6, 30),
        charges=[
            ("TC-06 charge A", "100.00", ChargeType.fee, date(2026, 6, 1)),
            ("TC-06 charge B", "100.00", ChargeType.fee, date(2026, 6, 2)),
        ],
    )
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "100.00",
            "paid_at": "2026-06-20T10:00:00Z",
            "method": "cash",
        },
    )
    assert response.status_code == 201
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.closed
    updated = list(db_session.execute(select(Charge).where(Charge.invoice_id == invoice.id).order_by(Charge.id)).scalars().all())
    all_student_charges = list(db_session.execute(select(Charge).where(Charge.student_id == student.id)).scalars().all())
    assert updated[0].status == ChargeStatus.paid
    assert updated[1].status == ChargeStatus.unpaid
    assert not any(charge.origin_charge_id is not None for charge in updated)
    assert not any(charge.invoice_id is None and charge.amount < 0 for charge in all_student_charges)
