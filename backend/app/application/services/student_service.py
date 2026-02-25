from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.errors import ConflictError, NotFoundError
from app.infrastructure.db.models import School, Student, StudentSchool, User, UserStudent
from app.interfaces.api.v1.schemas.student import StudentCreate, StudentUpdate


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
    return db.execute(select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))).scalar_one_or_none()


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
    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student: Student) -> None:
    student.deleted_at = datetime.now(timezone.utc)
    db.commit()


def associate_user_student(db: Session, user_id: int, student_id: int) -> UserStudent:
    user = db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()
    student = db.execute(select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))).scalar_one_or_none()
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
    student = db.execute(select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))).scalar_one_or_none()
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
