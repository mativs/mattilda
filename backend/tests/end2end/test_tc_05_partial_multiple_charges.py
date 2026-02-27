from datetime import date
from decimal import Decimal

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, setup_tc_context
from tests.helpers.factories import list_charges_for_student, list_negative_unpaid_carry_for_student, refresh_entity


def test_tc_05_partial_payment_multiple_charges(client, db_session, seeded_users):
    """
    Validate TC-05 partial payment across multiple charges.

    1. Seed charges 100, 50, 30 in one open invoice.
    2. Create payment of 120 through API.
    3. Validate first source charge is paid and carry credit -20 is created.
    4. Validate invoice is closed and later charges remain unpaid.
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
    refresh_entity(db_session, invoice)
    assert invoice.status == InvoiceStatus.closed
    all_charges = list_charges_for_student(db_session, student_id=student.id)
    carry_credit = list_negative_unpaid_carry_for_student(db_session, student_id=student.id)[0]
    source_by_id = {charge.id: charge for charge in all_charges if charge.id in [item.id for item in charges]}
    assert source_by_id[charges[0].id].status == ChargeStatus.paid
    assert source_by_id[charges[1].id].status == ChargeStatus.unpaid
    assert source_by_id[charges[2].id].status == ChargeStatus.unpaid
    assert carry_credit.status == ChargeStatus.unpaid
    assert carry_credit.amount == Decimal("-20.00")
