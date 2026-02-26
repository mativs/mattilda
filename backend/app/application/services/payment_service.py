from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.application.errors import NotFoundError, ValidationError
from app.infrastructure.db.models import Invoice, Payment, Student, StudentSchool, UserStudent
from app.interfaces.api.v1.schemas.payment import PaymentCreate


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
    get_student_in_school(db=db, student_id=payload.student_id, school_id=school_id)
    invoice = None
    if payload.invoice_id is not None:
        invoice = get_invoice_in_school(db=db, invoice_id=payload.invoice_id, school_id=school_id)
        if invoice.student_id != payload.student_id:
            raise ValidationError("Invoice does not belong to student")

    payment = Payment(
        school_id=school_id,
        student_id=payload.student_id,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        paid_at=payload.paid_at,
        method=payload.method,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


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
