from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.student_balance_service import invalidate_student_balance_cache
from app.application.errors import ValidationError
from app.application.services.charge_service import get_student_in_school
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge, Invoice, InvoiceItem
from app.infrastructure.logging import get_logger

MONTHLY_INTEREST_RATE = Decimal("0.02")
AVERAGE_MONTH_DAYS = Decimal("30")
logger = get_logger(__name__)


def _period_label(current_date: date) -> str:
    return f"{current_date.year:04d}-{current_date.month:02d}"


def _compute_accrued_interest(*, amount: Decimal, due_date: date, as_of: date) -> Decimal:
    overdue_days = Decimal((as_of - due_date).days)
    months_overdue = overdue_days / AVERAGE_MONTH_DAYS
    return (amount * MONTHLY_INTEREST_RATE * months_overdue).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_invoice_for_student(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    as_of: date | None = None,
) -> Invoice:
    as_of = as_of or datetime.now(timezone.utc).date()
    now_dt = datetime.now(timezone.utc)
    logger.info("invoice_generation_started", school_id=school_id, student_id=student_id, as_of=str(as_of))
    get_student_in_school(db=db, student_id=student_id, school_id=school_id)

    open_invoices = list(
        db.execute(
            select(Invoice).where(
                Invoice.school_id == school_id,
                Invoice.student_id == student_id,
                Invoice.status == InvoiceStatus.open,
                Invoice.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for open_invoice in open_invoices:
        open_invoice.status = InvoiceStatus.closed

    unpaid_charges = list(
        db.execute(
            select(Charge).where(
                Charge.school_id == school_id,
                Charge.student_id == student_id,
                Charge.status == ChargeStatus.unpaid,
                Charge.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )

    for base_charge in unpaid_charges:
        if (
            base_charge.charge_type != ChargeType.fee
            or base_charge.due_date >= as_of
            or base_charge.amount <= Decimal("0.00")
        ):
            continue
        accrued_total = _compute_accrued_interest(amount=base_charge.amount, due_date=base_charge.due_date, as_of=as_of)
        open_interest_total = sum(
            (
                charge.amount
                for charge in db.execute(
                    select(Charge).where(
                        Charge.school_id == school_id,
                        Charge.student_id == student_id,
                        Charge.origin_charge_id == base_charge.id,
                        Charge.charge_type == ChargeType.interest,
                        Charge.status == ChargeStatus.unpaid,
                        Charge.deleted_at.is_(None),
                    )
                )
                .scalars()
                .all()
            ),
            Decimal("0.00"),
        )
        delta = (accrued_total - open_interest_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if delta <= Decimal("0.00"):
            continue
        db.add(
            Charge(
                school_id=school_id,
                student_id=student_id,
                fee_definition_id=None,
                invoice_id=None,
                origin_charge_id=base_charge.id,
                description=f"Interest for charge #{base_charge.id}",
                amount=delta,
                period=base_charge.period,
                debt_created_at=now_dt,
                due_date=as_of,
                charge_type=ChargeType.interest,
                status=ChargeStatus.unpaid,
            )
        )

    db.flush()

    charges_for_invoice = list(
        db.execute(
            select(Charge).where(
                Charge.school_id == school_id,
                Charge.student_id == student_id,
                Charge.status == ChargeStatus.unpaid,
                Charge.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    if not charges_for_invoice:
        logger.warning("invoice_generation_skipped_no_unpaid_charges", school_id=school_id, student_id=student_id)
        raise ValidationError("No unpaid charges available for invoice generation")

    invoice = Invoice(
        school_id=school_id,
        student_id=student_id,
        period=_period_label(as_of),
        issued_at=now_dt,
        due_date=as_of,
        total_amount=Decimal("0.00"),
        status=InvoiceStatus.open,
    )
    db.add(invoice)
    db.flush()

    for charge in charges_for_invoice:
        charge.invoice_id = invoice.id
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                charge_id=charge.id,
                description=charge.description,
                amount=charge.amount,
                charge_type=charge.charge_type,
            )
        )
    invoice.total_amount = sum((charge.amount for charge in charges_for_invoice), Decimal("0.00")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    db.commit()
    db.refresh(invoice)
    invalidate_student_balance_cache(school_id=school_id, student_id=student_id)
    logger.info(
        "invoice_generation_completed",
        school_id=school_id,
        student_id=student_id,
        invoice_id=invoice.id,
        charges_count=len(charges_for_invoice),
        total_amount=str(invoice.total_amount),
    )
    return invoice
