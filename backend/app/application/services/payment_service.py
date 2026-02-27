from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.application.errors import NotFoundError, ValidationError
from app.application.services.student_balance_service import invalidate_student_balance_cache
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge, Invoice, Payment, Student, StudentSchool, UserStudent
from app.infrastructure.logging import get_logger
from app.interfaces.api.v1.schemas.payment import PaymentCreate

logger = get_logger(__name__)


def serialize_payment_response(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "school_id": payment.school_id,
        "student_id": payment.student_id,
        "invoice_id": payment.invoice_id,
        "amount": payment.amount,
        "paid_at": payment.paid_at,
        "method": payment.method,
        "created_at": payment.created_at,
        "updated_at": payment.updated_at,
        "student": {
            "id": payment.student.id,
            "first_name": payment.student.first_name,
            "last_name": payment.student.last_name,
        },
        "invoice": (
            {
                "id": payment.invoice.id,
                "period": payment.invoice.period,
                "status": payment.invoice.status,
            }
            if payment.invoice is not None
            else None
        ),
    }


def get_student_in_school(db: Session, *, student_id: int, school_id: int) -> Student:
    student = db.execute(
        select(Student)
        .join(StudentSchool, StudentSchool.student_id == Student.id)
        .where(
            Student.id == student_id,
            StudentSchool.school_id == school_id,
            Student.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if student is None:
        raise NotFoundError("Student not found")
    return student


def get_invoice_in_school(db: Session, *, invoice_id: int, school_id: int) -> Invoice:
    invoice = db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found")
    return invoice


def create_payment(db: Session, *, school_id: int, payload: PaymentCreate) -> Payment:
    logger.info(
        "payment_creation_started",
        school_id=school_id,
        student_id=payload.student_id,
        invoice_id=payload.invoice_id,
        amount=str(payload.amount),
    )
    get_student_in_school(db=db, student_id=payload.student_id, school_id=school_id)
    invoice = get_invoice_in_school(db=db, invoice_id=payload.invoice_id, school_id=school_id)
    if invoice.student_id != payload.student_id:
        logger.warning(
            "payment_creation_rejected_invoice_student_mismatch",
            school_id=school_id,
            student_id=payload.student_id,
            invoice_id=payload.invoice_id,
            invoice_student_id=invoice.student_id,
        )
        raise ValidationError("Invoice does not belong to student")
    if invoice.status != InvoiceStatus.open:
        logger.warning(
            "payment_creation_rejected_invoice_not_open",
            school_id=school_id,
            student_id=payload.student_id,
            invoice_id=payload.invoice_id,
            invoice_status=invoice.status,
        )
        raise ValidationError("Only open invoices can receive payments")
    if payload.paid_at.date() > invoice.due_date:
        logger.warning(
            "payment_creation_rejected_overdue_invoice",
            school_id=school_id,
            student_id=payload.student_id,
            invoice_id=payload.invoice_id,
            paid_at=str(payload.paid_at),
            due_date=str(invoice.due_date),
        )
        raise ValidationError("Overdue invoices cannot receive payments")

    payment = Payment(
        school_id=school_id,
        student_id=payload.student_id,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        paid_at=payload.paid_at,
        method=payload.method,
    )
    db.add(payment)
    db.flush()
    _allocate_payment_to_invoice(db=db, invoice=invoice, payment=payment)
    db.refresh(payment)
    invalidate_student_balance_cache(school_id=school_id, student_id=payload.student_id)
    logger.info(
        "payment_creation_completed",
        school_id=school_id,
        student_id=payload.student_id,
        invoice_id=payload.invoice_id,
        payment_id=payment.id,
        amount=str(payment.amount),
    )
    return payment


def _sorted_positive_charges(charges: list[Charge]) -> list[Charge]:
    return sorted(charges, key=lambda charge: (charge.debt_created_at, -charge.amount, charge.id))


def _allocate_payment_to_invoice(db: Session, *, invoice: Invoice, payment: Payment) -> None:
    invoice_charges = list(
        db.execute(
            select(Charge).where(
                Charge.invoice_id == invoice.id,
                Charge.school_id == invoice.school_id,
                Charge.deleted_at.is_(None),
                Charge.status != ChargeStatus.cancelled,
            )
        )
        .scalars()
        .all()
    )
    negative_unpaid = [
        charge for charge in invoice_charges if charge.amount < Decimal("0.00") and charge.status == ChargeStatus.unpaid
    ]
    positive_unpaid = [
        charge for charge in invoice_charges if charge.amount > Decimal("0.00") and charge.status == ChargeStatus.unpaid
    ]

    credit_from_negative = sum((charge.amount.copy_abs() for charge in negative_unpaid), Decimal("0.00"))
    total_allocatable = payment.amount + credit_from_negative
    total_allocatable = total_allocatable.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    for charge in negative_unpaid:
        charge.status = ChargeStatus.paid

    remaining = total_allocatable
    for charge in _sorted_positive_charges(positive_unpaid):
        if remaining <= Decimal("0.00"):
            break
        if remaining >= charge.amount:
            charge.status = ChargeStatus.paid
            remaining -= charge.amount
            continue
        # Do not split charge on partial cutoff; keep charge unpaid
        break

    carry_credit_amount = remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if carry_credit_amount > Decimal("0.00"):
        db.add(
            Charge(
                school_id=invoice.school_id,
                student_id=invoice.student_id,
                fee_definition_id=None,
                invoice_id=None,
                origin_charge_id=None,
                description=f"Carry credit from invoice #{invoice.id}",
                amount=(carry_credit_amount * Decimal("-1")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                period=invoice.period,
                debt_created_at=datetime.now(timezone.utc),
                due_date=invoice.due_date,
                charge_type=ChargeType.penalty,
                status=ChargeStatus.unpaid,
            )
        )
    invoice.status = InvoiceStatus.closed
    db.commit()


def get_visible_student_for_payment_access(
    db: Session,
    *,
    student_id: int,
    school_id: int,
    user_id: int,
    is_admin: bool,
) -> Student | None:
    query = (
        select(Student)
        .join(StudentSchool, StudentSchool.student_id == Student.id)
        .where(
            Student.id == student_id,
            StudentSchool.school_id == school_id,
            Student.deleted_at.is_(None),
        )
    )
    if not is_admin:
        query = query.join(UserStudent, UserStudent.student_id == Student.id).where(UserStudent.user_id == user_id)
    return db.execute(query).scalar_one_or_none()


def build_visible_payments_query_for_student(
    *,
    student_id: int,
    school_id: int,
    user_id: int,
    is_admin: bool,
):
    query = (
        select(Payment)
        .join(Student, Student.id == Payment.student_id)
        .where(
            Payment.school_id == school_id,
            Payment.student_id == student_id,
            Payment.deleted_at.is_(None),
        )
        .options(selectinload(Payment.student), selectinload(Payment.invoice))
        .order_by(Payment.paid_at.desc(), Payment.id.desc())
    )
    if not is_admin:
        query = query.join(UserStudent, UserStudent.student_id == Payment.student_id).where(
            UserStudent.user_id == user_id
        )
    return query


def get_visible_payment_by_id(
    db: Session,
    *,
    payment_id: int,
    school_id: int,
    user_id: int,
    is_admin: bool,
) -> Payment | None:
    query = (
        select(Payment)
        .where(
            Payment.id == payment_id,
            Payment.school_id == school_id,
            Payment.deleted_at.is_(None),
        )
        .options(selectinload(Payment.student), selectinload(Payment.invoice))
    )
    if not is_admin:
        query = query.join(UserStudent, UserStudent.student_id == Payment.student_id).where(
            UserStudent.user_id == user_id
        )
    return db.execute(query).scalar_one_or_none()
