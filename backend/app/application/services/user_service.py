from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.roles import UserRole
from app.infrastructure.db.models import User, UserProfile
from app.interfaces.api.v1.schemas.user import UserCreate, UserUpdate


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def create_user(db: Session, payload: UserCreate) -> User:
    existing_user = get_user_by_email(db=db, email=payload.email)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_active=payload.is_active,
    )
    user.profile = UserProfile(
        first_name=payload.profile.first_name,
        last_name=payload.profile.last_name,
        phone=payload.profile.phone,
        address=payload.profile.address,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, payload: UserUpdate) -> User:
    if payload.email is not None and payload.email != user.email:
        existing_user = get_user_by_email(db=db, email=payload.email)
        if existing_user is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user.email = payload.email

    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)

    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.profile is not None:
        if payload.profile.first_name is not None:
            user.profile.first_name = payload.profile.first_name
        if payload.profile.last_name is not None:
            user.profile.last_name = payload.profile.last_name
        if payload.profile.phone is not None:
            user.profile.phone = payload.profile.phone
        if payload.profile.address is not None:
            user.profile.address = payload.profile.address

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False
    db.commit()


def get_user_school_roles(user: User) -> list[dict]:
    grouped_roles: dict[int, dict] = {}
    for membership in user.school_memberships:
        school_id = membership.school_id
        if school_id not in grouped_roles:
            grouped_roles[school_id] = {
                "school_id": school_id,
                "school_name": membership.school.name,
                "roles": [],
            }
        grouped_roles[school_id]["roles"].append(UserRole(membership.role))

    return list(grouped_roles.values())


def serialize_user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "profile": user.profile,
        "schools": get_user_school_roles(user),
        "students": get_user_students(user),
    }


def get_user_students(user: User) -> list[dict]:
    students: dict[int, dict] = {}
    for link in user.student_links:
        if link.student.deleted_at is not None:
            continue
        if link.student_id not in students:
            students[link.student_id] = {
                "id": link.student.id,
                "first_name": link.student.first_name,
                "last_name": link.student.last_name,
                "external_id": link.student.external_id,
                "school_ids": [],
            }
        school_ids = [school_link.school_id for school_link in link.student.school_links if school_link.school.deleted_at is None]
        students[link.student_id]["school_ids"] = sorted(set(school_ids))
    return list(students.values())
