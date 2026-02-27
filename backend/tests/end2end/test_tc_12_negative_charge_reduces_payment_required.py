from datetime import date

from sqlalchemy import select

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context


def test_tc_12_negative_charge_reduces_payment_required(client, db_session, seeded_users):
    """
    Validate TC-12 negative carry reduces required payment.

    1. Seed invoice with positive 100 charge and negative carry -20.
    2. Create payment of 80 through API.
    3. Validate invoice closes.
    4. Validate negative charge is marked paid.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="12")
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-12",
        due_date=date(2026, 12, 31),
        charges=[
            ("TC-12 fee", "100.00", ChargeType.fee, date(2026, 12, 1)),
            ("TC-12 carry", "-20.00", ChargeType.penalty, date(2026, 12, 1)),
        ],
    )
    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "student_id": student.id,
            "invoice_id": invoice.id,
            "amount": "80.00",
            "paid_at": "2026-12-20T10:00:00Z",
            "method": "cash",
        },
    )
    assert response.status_code == 201
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.closed
    negative = db_session.execute(
        select(Charge).where(Charge.invoice_id == invoice.id, Charge.amount < 0, Charge.deleted_at.is_(None))
    ).scalar_one()
    assert negative.status == ChargeStatus.paid
