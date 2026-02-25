from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.roles import UserRole
from app.infrastructure.db.models import School, User, UserProfile, UserSchoolRole
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

        create_membership_if_missing(db=db, user_id=admin.id, school_id=north_school.id, role=UserRole.director)
        create_membership_if_missing(db=db, user_id=admin.id, school_id=south_school.id, role=UserRole.director)
        create_membership_if_missing(db=db, user_id=teacher.id, school_id=north_school.id, role=UserRole.teacher)
        create_membership_if_missing(db=db, user_id=teacher.id, school_id=south_school.id, role=UserRole.teacher)
        create_membership_if_missing(db=db, user_id=student.id, school_id=north_school.id, role=UserRole.student)

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
