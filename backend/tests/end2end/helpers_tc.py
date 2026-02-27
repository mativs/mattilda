from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.domain.roles import UserRole
from app.infrastructure.db.models import Charge, Invoice
from tests.helpers.auth import school_header, token_for_user
from tests.helpers.factories import add_membership, create_charge, create_invoice, create_invoice_item, create_school, create_student, link_student_school


def setup_tc_context(db: Session, seeded_users: dict, *, tc_code: str):
    school = create_school(db, f"TC Lab {tc_code}", f"tc-lab-{tc_code.lower()}")
    add_membership(db, seeded_users["admin"].id, school.id, UserRole.admin)
    student = create_student(db, f"TC{tc_code}", "Student", f"TC-{tc_code}-STU")
    link_student_school(db, student.id, school.id)
    headers = school_header(token_for_user(seeded_users["admin"].id), school.id)
    return school, student, headers


def create_open_invoice_with_charges(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    period: str,
    due_date: date,
    charges: list[tuple[str, str, ChargeType, date]],
) -> tuple[Invoice, list[Charge]]:
    created_charges: list[Charge] = []
    total = Decimal("0.00")
    for idx, (description, amount, charge_type, debt_date) in enumerate(charges, start=1):
        charge = create_charge(
            db,
            school_id=school_id,
            student_id=student_id,
            description=description,
            amount=amount,
            due_date=due_date,
            charge_type=charge_type,
            status=ChargeStatus.unpaid,
            period=period,
            debt_created_at=datetime(debt_date.year, debt_date.month, debt_date.day, 9, 0, tzinfo=timezone.utc),
        )
        created_charges.append(charge)
        total += Decimal(amount)
    invoice = create_invoice(
        db,
        school_id=school_id,
        student_id=student_id,
        period=period,
        issued_at=datetime(due_date.year, due_date.month, 1, tzinfo=timezone.utc),
        due_date=due_date,
        total_amount=f"{total:.2f}",
        status=InvoiceStatus.open,
    )
    for charge in created_charges:
        charge.invoice_id = invoice.id
        create_invoice_item(
            db,
            invoice_id=invoice.id,
            charge_id=charge.id,
            description=charge.description,
            amount=f"{charge.amount:.2f}",
            charge_type=charge.charge_type,
        )
    db.commit()
    db.refresh(invoice)
    refreshed = list(db.execute(select(Charge).where(Charge.invoice_id == invoice.id)).scalars().all())
    return invoice, refreshed


def get_invoice_charges(db: Session, *, invoice_id: int) -> list[Charge]:
    return list(
        db.execute(select(Charge).where(Charge.invoice_id == invoice_id, Charge.deleted_at.is_(None)).order_by(Charge.id))
        .scalars()
        .all()
    )
