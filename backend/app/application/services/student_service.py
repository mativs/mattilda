from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.errors import ConflictError, NotFoundError
from app.application.services.association_sync_service import apply_partial_sync_operations_from_existing_keys
from app.application.services.student_balance_service import get_student_balance_snapshot
from app.infrastructure.db.models import School, Student, StudentSchool, User, UserStudent
from app.infrastructure.logging import get_logger
from app.interfaces.api.v1.schemas.student import StudentAssociationsUpdate, StudentCreate, StudentUpdate

logger = get_logger(__name__)


def list_students_for_school(db: Session, school_id: int) -> list[Student]:
    return list(
        db.execute(
            select(Student)
            .join(StudentSchool, StudentSchool.student_id == Student.id)
            .where(StudentSchool.school_id == school_id, Student.deleted_at.is_(None))
            .order_by(Student.id)
        )
        .scalars()
        .all()
    )


def list_students_for_user_in_school(db: Session, user_id: int, school_id: int) -> list[Student]:
    return list(
        db.execute(
            select(Student)
            .join(StudentSchool, StudentSchool.student_id == Student.id)
            .join(UserStudent, UserStudent.student_id == Student.id)
            .where(
                StudentSchool.school_id == school_id,
                UserStudent.user_id == user_id,
                Student.deleted_at.is_(None),
            )
            .order_by(Student.id)
        )
        .scalars()
        .all()
    )


def get_student_by_id(db: Session, student_id: int) -> Student | None:
    return db.execute(
        select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))
    ).scalar_one_or_none()


def get_visible_student_for_user(
    db: Session, student_id: int, school_id: int, user_id: int, is_admin: bool
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


def serialize_student_response(student: Student) -> dict:
    user_ids = sorted({link.user_id for link in student.user_links if link.user.deleted_at is None})
    school_ids = sorted({link.school_id for link in student.school_links if link.school.deleted_at is None})
    users = []
    for link in student.user_links:
        if link.user.deleted_at is not None:
            continue
        full_name = f"{link.user.profile.first_name} {link.user.profile.last_name}".strip()
        users.append({"id": link.user_id, "name": full_name, "email": link.user.email})
    schools = []
    for link in student.school_links:
        if link.school.deleted_at is not None:
            continue
        schools.append({"id": link.school_id, "name": link.school.name, "slug": link.school.slug})
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "external_id": student.external_id,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
        "user_ids": user_ids,
        "school_ids": school_ids,
        "users": sorted(users, key=lambda item: item["id"]),
        "schools": sorted(schools, key=lambda item: item["id"]),
    }


def create_student(db: Session, payload: StudentCreate) -> Student:
    if payload.external_id is not None:
        existing = db.execute(
            select(Student).where(Student.external_id == payload.external_id, Student.deleted_at.is_(None))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Student external_id already exists")

    student = Student(first_name=payload.first_name, last_name=payload.last_name, external_id=payload.external_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def create_student_for_school(db: Session, payload: StudentCreate, school_id: int) -> Student:
    school = db.execute(select(School).where(School.id == school_id, School.deleted_at.is_(None))).scalar_one_or_none()
    if school is None:
        raise NotFoundError("School not found")

    student = create_student(db=db, payload=payload)
    db.add(StudentSchool(student_id=student.id, school_id=school_id))
    db.commit()
    db.refresh(student)
    return student


def update_student(db: Session, student: Student, payload: StudentUpdate) -> Student:
    if payload.external_id is not None and payload.external_id != student.external_id:
        existing = db.execute(
            select(Student).where(Student.external_id == payload.external_id, Student.deleted_at.is_(None))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Student external_id already exists")
        student.external_id = payload.external_id
    if payload.first_name is not None:
        student.first_name = payload.first_name
    if payload.last_name is not None:
        student.last_name = payload.last_name

    if payload.associations is not None:
        apply_student_association_updates(db=db, student=student, associations=payload.associations)

    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student: Student) -> None:
    student.deleted_at = datetime.now(timezone.utc)
    db.commit()


def associate_user_student(db: Session, user_id: int, student_id: int) -> UserStudent:
    user = db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")
    if student is None:
        raise NotFoundError("Student not found")

    existing = db.execute(
        select(UserStudent).where(UserStudent.user_id == user_id, UserStudent.student_id == student_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Association already exists")

    link = UserStudent(user_id=user_id, student_id=student_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def deassociate_user_student(db: Session, user_id: int, student_id: int) -> None:
    link = db.execute(
        select(UserStudent).where(UserStudent.user_id == user_id, UserStudent.student_id == student_id)
    ).scalar_one_or_none()
    if link is None:
        raise NotFoundError("Association not found")
    db.delete(link)
    db.commit()


def associate_student_school(db: Session, student_id: int, school_id: int) -> StudentSchool:
    school = db.execute(select(School).where(School.id == school_id, School.deleted_at.is_(None))).scalar_one_or_none()
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))
    ).scalar_one_or_none()
    if school is None:
        raise NotFoundError("School not found")
    if student is None:
        raise NotFoundError("Student not found")

    existing = db.execute(
        select(StudentSchool).where(StudentSchool.student_id == student_id, StudentSchool.school_id == school_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Association already exists")

    link = StudentSchool(student_id=student_id, school_id=school_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def deassociate_student_school(db: Session, student_id: int, school_id: int) -> None:
    link = db.execute(
        select(StudentSchool).where(StudentSchool.student_id == student_id, StudentSchool.school_id == school_id)
    ).scalar_one_or_none()
    if link is None:
        raise NotFoundError("Association not found")
    db.delete(link)
    db.commit()


def _student_user_link_key(value: int) -> str:
    return str(value)


def _student_school_link_key(value: int) -> str:
    return str(value)


def apply_student_association_updates(db: Session, student: Student, associations: StudentAssociationsUpdate) -> None:
    existing_user_links = list(
        db.execute(select(UserStudent).where(UserStudent.student_id == student.id)).scalars().all()
    )
    existing_school_links = list(
        db.execute(select(StudentSchool).where(StudentSchool.student_id == student.id)).scalars().all()
    )
    existing_user_keys = {str(link.user_id) for link in existing_user_links}
    existing_school_keys = {str(link.school_id) for link in existing_school_links}

    def apply_add_user(user_id: int) -> None:
        user = db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found")
        db.add(UserStudent(user_id=user_id, student_id=student.id))

    def apply_remove_user(user_id: int) -> None:
        link = db.execute(
            select(UserStudent).where(UserStudent.user_id == user_id, UserStudent.student_id == student.id)
        ).scalar_one_or_none()
        if link is not None:
            db.delete(link)

    def apply_add_school(school_id: int) -> None:
        school = db.execute(
            select(School).where(School.id == school_id, School.deleted_at.is_(None))
        ).scalar_one_or_none()
        if school is None:
            raise NotFoundError("School not found")
        db.add(StudentSchool(student_id=student.id, school_id=school_id))

    def apply_remove_school(school_id: int) -> None:
        link = db.execute(
            select(StudentSchool).where(StudentSchool.student_id == student.id, StudentSchool.school_id == school_id)
        ).scalar_one_or_none()
        if link is not None:
            db.delete(link)

    apply_partial_sync_operations_from_existing_keys(
        existing_keys=existing_user_keys,
        to_add=associations.add.user_ids,
        to_remove=associations.remove.user_ids,
        key_fn=_student_user_link_key,
        apply_add=apply_add_user,
        apply_remove=apply_remove_user,
    )
    apply_partial_sync_operations_from_existing_keys(
        existing_keys=existing_school_keys,
        to_add=associations.add.school_ids,
        to_remove=associations.remove.school_ids,
        key_fn=_student_school_link_key,
        apply_add=apply_add_school,
        apply_remove=apply_remove_school,
    )


def get_student_financial_summary(db: Session, *, school_id: int, student_id: int) -> dict:
    snapshot = get_student_balance_snapshot(db=db, school_id=school_id, student_id=student_id)
    total_unpaid_amount = snapshot["total_unpaid_amount"]
    total_unpaid_debt_amount = snapshot["total_unpaid_debt_amount"]
    total_unpaid_credit_amount = snapshot["total_unpaid_credit_amount"]
    total_charged_amount = snapshot["total_charged_amount"]
    total_paid_amount = snapshot["total_paid_amount"]

    summary = {
        "total_unpaid_amount": total_unpaid_amount,
        "total_unpaid_debt_amount": total_unpaid_debt_amount,
        "total_unpaid_credit_amount": total_unpaid_credit_amount,
        "total_charged_amount": total_charged_amount,
        "total_paid_amount": total_paid_amount,
        "account_status": "ok" if total_unpaid_amount <= Decimal("0.00") else "owes",
    }
    logger.info(
        "student_financial_summary_computed",
        school_id=school_id,
        student_id=student_id,
        total_unpaid_amount=str(summary["total_unpaid_amount"]),
        total_charged_amount=str(summary["total_charged_amount"]),
        total_paid_amount=str(summary["total_paid_amount"]),
        account_status=summary["account_status"],
    )
    return summary
