from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.fee_recurrence import FeeRecurrence
from app.domain.roles import UserRole
from app.infrastructure.db.models import FeeDefinition, School, Student, StudentSchool, User, UserProfile, UserSchoolRole, UserStudent
from app.infrastructure.db.session import SessionLocal


def create_user_if_missing(
    db: Session,
    email: str,
    password: str,
    profile: tuple[str, str],
) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        return existing

    user = User(email=email, hashed_password=hash_password(password), is_active=True)
    user.profile = UserProfile(first_name=profile[0], last_name=profile[1])
    db.add(user)
    db.flush()
    return user


def create_school_if_missing(db: Session, name: str, slug: str) -> School:
    school = db.execute(select(School).where(School.slug == slug)).scalar_one_or_none()
    if school is not None:
        return school

    school = School(name=name, slug=slug, is_active=True)
    db.add(school)
    db.flush()
    return school


def create_membership_if_missing(db: Session, user_id: int, school_id: int, role: UserRole) -> None:
    existing = db.execute(
        select(UserSchoolRole).where(
            UserSchoolRole.user_id == user_id,
            UserSchoolRole.school_id == school_id,
            UserSchoolRole.role == role.value,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(UserSchoolRole(user_id=user_id, school_id=school_id, role=role.value))


def create_student_if_missing(db: Session, first_name: str, last_name: str, external_id: str) -> Student:
    student = db.execute(select(Student).where(Student.external_id == external_id, Student.deleted_at.is_(None))).scalar_one_or_none()
    if student is not None:
        return student
    student = Student(first_name=first_name, last_name=last_name, external_id=external_id)
    db.add(student)
    db.flush()
    return student


def associate_student_school_if_missing(db: Session, student_id: int, school_id: int) -> None:
    existing = db.execute(
        select(StudentSchool).where(StudentSchool.student_id == student_id, StudentSchool.school_id == school_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(StudentSchool(student_id=student_id, school_id=school_id))


def associate_user_student_if_missing(db: Session, user_id: int, student_id: int) -> None:
    existing = db.execute(
        select(UserStudent).where(UserStudent.user_id == user_id, UserStudent.student_id == student_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(UserStudent(user_id=user_id, student_id=student_id))


def create_fee_if_missing(
    db: Session,
    *,
    school_id: int,
    name: str,
    amount: Decimal,
    recurrence: FeeRecurrence,
    is_active: bool = True,
) -> FeeDefinition:
    existing = db.execute(
        select(FeeDefinition).where(
            FeeDefinition.school_id == school_id,
            FeeDefinition.name == name,
            FeeDefinition.recurrence == recurrence,
            FeeDefinition.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    fee = FeeDefinition(
        school_id=school_id,
        name=name,
        amount=amount,
        recurrence=recurrence,
        is_active=is_active,
    )
    db.add(fee)
    db.flush()
    return fee


def main() -> None:
    db = SessionLocal()
    try:
        north_school = create_school_if_missing(db=db, name="North High", slug="north-high")
        south_school = create_school_if_missing(db=db, name="South High", slug="south-high")

        admin = create_user_if_missing(
            db=db,
            email="admin@example.com",
            password="admin123",
            profile=("Admin", "User"),
        )
        teacher = create_user_if_missing(
            db=db,
            email="teacher@example.com",
            password="teacher123",
            profile=("Teacher", "User"),
        )
        student = create_user_if_missing(
            db=db,
            email="student@example.com",
            password="student123",
            profile=("Student", "User"),
        )

        create_membership_if_missing(db=db, user_id=admin.id, school_id=north_school.id, role=UserRole.admin)
        create_membership_if_missing(db=db, user_id=admin.id, school_id=south_school.id, role=UserRole.admin)
        create_membership_if_missing(db=db, user_id=teacher.id, school_id=north_school.id, role=UserRole.teacher)
        create_membership_if_missing(db=db, user_id=teacher.id, school_id=south_school.id, role=UserRole.teacher)
        create_membership_if_missing(db=db, user_id=student.id, school_id=north_school.id, role=UserRole.student)

        child_one = create_student_if_missing(db=db, first_name="Alice", last_name="Student", external_id="STU-001")
        child_two = create_student_if_missing(db=db, first_name="Bob", last_name="Student", external_id="STU-002")

        associate_student_school_if_missing(db=db, student_id=child_one.id, school_id=north_school.id)
        associate_student_school_if_missing(db=db, student_id=child_two.id, school_id=north_school.id)
        associate_student_school_if_missing(db=db, student_id=child_two.id, school_id=south_school.id)
        associate_user_student_if_missing(db=db, user_id=student.id, student_id=child_one.id)
        associate_user_student_if_missing(db=db, user_id=student.id, student_id=child_two.id)
        associate_user_student_if_missing(db=db, user_id=teacher.id, student_id=child_two.id)

        create_fee_if_missing(
            db=db,
            school_id=north_school.id,
            name="Cuota mensual",
            amount=Decimal("150.00"),
            recurrence=FeeRecurrence.monthly,
        )
        create_fee_if_missing(
            db=db,
            school_id=north_school.id,
            name="Matrícula",
            amount=Decimal("450.00"),
            recurrence=FeeRecurrence.annual,
        )
        create_fee_if_missing(
            db=db,
            school_id=south_school.id,
            name="Materiales",
            amount=Decimal("95.00"),
            recurrence=FeeRecurrence.one_time,
        )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
