from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.infrastructure.db.models import Invoice, InvoiceItem, Student, StudentSchool, UserStudent


def serialize_invoice_summary(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "school_id": invoice.school_id,
        "student_id": invoice.student_id,
        "period": invoice.period,
        "issued_at": invoice.issued_at,
        "due_date": invoice.due_date,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
        "student": {
            "id": invoice.student.id,
            "first_name": invoice.student.first_name,
            "last_name": invoice.student.last_name,
        },
    }


def serialize_invoice_detail(invoice: Invoice) -> dict:
    payload = serialize_invoice_summary(invoice)
    payload["items"] = [
        {
            "id": item.id,
            "invoice_id": item.invoice_id,
            "charge_id": item.charge_id,
            "description": item.description,
            "amount": item.amount,
            "charge_type": item.charge_type,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in sorted(invoice.items, key=lambda current: current.id)
    ]
    return payload


def get_visible_student_for_invoice_access(
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


def build_visible_invoices_query_for_student(
    *,
    student_id: int,
    school_id: int,
    user_id: int,
    is_admin: bool,
):
    query = (
        select(Invoice)
        .join(Student, Student.id == Invoice.student_id)
        .where(
            Invoice.school_id == school_id,
            Invoice.student_id == student_id,
            Invoice.deleted_at.is_(None),
        )
        .options(selectinload(Invoice.student))
        .order_by(Invoice.id.desc())
    )
    if not is_admin:
        query = query.join(UserStudent, UserStudent.student_id == Invoice.student_id).where(
            UserStudent.user_id == user_id
        )
    return query


def get_visible_invoice_by_id(
    db: Session,
    *,
    invoice_id: int,
    school_id: int,
    user_id: int,
    is_admin: bool,
) -> Invoice | None:
    query = (
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
        )
        .options(selectinload(Invoice.student), selectinload(Invoice.items))
    )
    if not is_admin:
        query = query.join(UserStudent, UserStudent.student_id == Invoice.student_id).where(
            UserStudent.user_id == user_id
        )
    return db.execute(query).scalar_one_or_none()


def get_visible_invoice_items(
    db: Session,
    *,
    invoice_id: int,
    school_id: int,
    user_id: int,
    is_admin: bool,
) -> list[InvoiceItem] | None:
    invoice = get_visible_invoice_by_id(
        db=db,
        invoice_id=invoice_id,
        school_id=school_id,
        user_id=user_id,
        is_admin=is_admin,
    )
    if invoice is None:
        return None
    return sorted(invoice.items, key=lambda item: item.id)
