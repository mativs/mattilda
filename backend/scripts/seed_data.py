from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.roles import UserRole
from app.infrastructure.db.models import User, UserProfile
from app.infrastructure.db.session import SessionLocal


def create_user_if_missing(
    db: Session,
    email: str,
    password: str,
    roles: Sequence[UserRole],
    profiles: Sequence[tuple[str, str]],
) -> None:
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        return

    user = User(
        email=email,
        hashed_password=hash_password(password),
        roles=[role.value for role in roles],
        is_active=True,
    )
    user.profile = UserProfile(first_name=profiles[0][0], last_name=profiles[0][1])
    db.add(user)


def main() -> None:
    db = SessionLocal()
    try:
        create_user_if_missing(
            db=db,
            email="admin@example.com",
            password="admin123",
            roles=[UserRole.admin, UserRole.director],
            profiles=[("Admin", "User")],
        )
        create_user_if_missing(
            db=db,
            email="teacher@example.com",
            password="teacher123",
            roles=[UserRole.teacher],
            profiles=[("Teacher", "User")],
        )
        create_user_if_missing(
            db=db,
            email="student@example.com",
            password="student123",
            roles=[UserRole.student],
            profiles=[("Student", "User")],
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
