from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context
from tests.helpers.factories import (
    commit_session,
    create_charge,
    create_invoice,
    create_invoice_item,
    create_payment,
    get_negative_charge_for_invoice,
    refresh_entity,
)


def test_tc_12_negative_charge_reduces_payment_required(client, db_session, seeded_users):
    """
    Validate TC-12 negative carry reduces required payment.

    1. Seed prior period overpayment that generates a legitimate -20 carry.
    2. Seed current invoice with +100 fee and the -20 carry.
    3. Create payment of 80 through API.
    4. Validate invoice closes and negative charge is marked paid.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="12")
    prior_charge = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-12 prior fee paid",
        amount="100.00",
        due_date=date(2026, 11, 10),
        charge_type=ChargeType.fee,
        status=ChargeStatus.paid,
        period="2026-11",
        debt_created_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
    )
    prior_invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-11",
        issued_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        due_date=date(2026, 11, 10),
        total_amount="100.00",
        status=InvoiceStatus.closed,
    )
    prior_charge.invoice_id = prior_invoice.id
    create_invoice_item(
        db_session,
        invoice_id=prior_invoice.id,
        charge_id=prior_charge.id,
        description=prior_charge.description,
        amount="100.00",
        charge_type=ChargeType.fee,
    )
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        invoice_id=prior_invoice.id,
        amount="120.00",
        paid_at=datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc),
        method="transfer",
    )
    carry = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="TC-12 carry",
        amount="-20.00",
        due_date=date(2026, 12, 31),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
        period="2026-12",
        debt_created_at=datetime(2026, 11, 12, 12, 1, tzinfo=timezone.utc),
    )
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-12",
        due_date=date(2026, 12, 31),
        charges=[("TC-12 fee", "100.00", ChargeType.fee, date(2026, 12, 1))],
    )
    carry.invoice_id = invoice.id
    create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=carry.id,
        description=carry.description,
        amount="-20.00",
        charge_type=carry.charge_type,
    )
    invoice.total_amount = Decimal("80.00")
    commit_session(db_session)
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
    refresh_entity(db_session, invoice)
    assert invoice.status == InvoiceStatus.closed
    negative = get_negative_charge_for_invoice(db_session, invoice_id=invoice.id)
    assert negative.status == ChargeStatus.paid
