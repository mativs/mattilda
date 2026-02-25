from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.infrastructure.db.models import User, UserProfile
from app.interfaces.api.v1.schemas.user import UserCreate, UserUpdate


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def list_users(db: Session) -> list[User]:
    return db.execute(select(User).order_by(User.id)).scalars().all()


def create_user(db: Session, payload: UserCreate) -> User:
    existing_user = get_user_by_email(db=db, email=payload.email)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        roles=[role.value for role in payload.roles],
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

    if payload.roles is not None:
        user.roles = [role.value for role in payload.roles]

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
    db.delete(user)
    db.commit()
