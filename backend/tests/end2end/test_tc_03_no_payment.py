from datetime import date

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from tests.end2end.helpers_tc import create_open_invoice_with_charges, get_invoice_charges, setup_tc_context
from tests.helpers.factories import refresh_entity


def test_tc_03_no_payment(client, db_session, seeded_users):
    """
    Validate TC-03 invoice without payments.

    1. Seed one open invoice with an unpaid fee charge.
    2. Call invoice detail endpoint once through API.
    3. Validate invoice remains open.
    4. Validate charge remains unpaid.
    """
    school, student, headers = setup_tc_context(db_session, seeded_users, tc_code="03")
    invoice, _ = create_open_invoice_with_charges(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-03",
        due_date=date(2026, 3, 31),
        charges=[("TC-03 fee", "100.00", ChargeType.fee, date(2026, 3, 1))],
    )
    response = client.get(f"/api/v1/invoices/{invoice.id}", headers=headers)
    assert response.status_code == 200
    refresh_entity(db_session, invoice)
    assert invoice.status == InvoiceStatus.open
    charges = get_invoice_charges(db_session, invoice_id=invoice.id)
    assert charges[0].status == ChargeStatus.unpaid
