from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.errors import ValidationError
from app.application.services.invoice_generation_service import generate_invoice_for_student
from app.infrastructure.db.models import Student, StudentSchool


def generate_invoices_for_school(
    db: Session,
    *,
    school_id: int,
    as_of: date | None = None,
) -> dict:
    student_ids = list(
        db.execute(
            select(Student.id)
            .join(StudentSchool, StudentSchool.student_id == Student.id)
            .where(StudentSchool.school_id == school_id, Student.deleted_at.is_(None))
            .order_by(Student.id)
        )
        .scalars()
        .all()
    )
    generated_students = 0
    skipped_students = 0
    failed_students = 0
    errors: list[dict] = []
    for student_id in student_ids:
        try:
            generate_invoice_for_student(db=db, school_id=school_id, student_id=student_id, as_of=as_of)
            generated_students += 1
        except ValidationError as exc:
            db.rollback()
            skipped_students += 1
            errors.append({"student_id": student_id, "error": str(exc), "type": "skipped"})
        except Exception as exc:
            db.rollback()
            failed_students += 1
            errors.append({"student_id": student_id, "error": str(exc), "type": "failed"})
    return {
        "school_id": school_id,
        "processed_students": len(student_ids),
        "generated_students": generated_students,
        "skipped_students": skipped_students,
        "failed_students": failed_students,
        "errors": errors,
    }
