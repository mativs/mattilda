from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.domain.roles import UserRole
from app.infrastructure.db.models import School, User, UserSchoolRole
from app.interfaces.api.v1.schemas.school import SchoolCreate, SchoolUpdate


def _build_member_map(school: School) -> list[dict]:
    grouped: dict[int, dict] = {}
    for membership in school.members:
        if membership.user.deleted_at is not None:
            continue
        if membership.user_id not in grouped:
            grouped[membership.user_id] = {
                "user_id": membership.user_id,
                "email": membership.user.email,
                "roles": [],
            }
        grouped[membership.user_id]["roles"].append(UserRole(membership.role))
    return list(grouped.values())


def serialize_school_response(school: School) -> dict:
    return {
        "id": school.id,
        "name": school.name,
        "slug": school.slug,
        "is_active": school.is_active,
        "created_at": school.created_at,
        "updated_at": school.updated_at,
        "members": _build_member_map(school),
    }


def _replace_memberships(db: Session, school: School, members_payload: list) -> None:
    db.execute(delete(UserSchoolRole).where(UserSchoolRole.school_id == school.id))
    if not members_payload:
        return

    user_ids = [member.user_id for member in members_payload]
    existing_users = db.execute(select(User).where(User.id.in_(user_ids), User.deleted_at.is_(None))).scalars().all()
    existing_by_id = {user.id: user for user in existing_users}
    missing_user_ids = sorted(set(user_ids) - set(existing_by_id))
    if missing_user_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Users not found: {missing_user_ids}",
        )

    memberships: list[UserSchoolRole] = []
    for member in members_payload:
        for role in member.roles:
            memberships.append(
                UserSchoolRole(
                    user_id=member.user_id,
                    school_id=school.id,
                    role=role.value,
                )
            )
    db.add_all(memberships)


def get_school_by_id(db: Session, school_id: int) -> School | None:
    return (
        db.execute(
            select(School)
            .where(School.id == school_id, School.deleted_at.is_(None))
            .options(joinedload(School.members).joinedload(UserSchoolRole.user))
        )
        .unique()
        .scalar_one_or_none()
    )


def list_schools_for_user(db: Session, user: User) -> list[School]:
    query = (
        select(School)
        .join(UserSchoolRole, UserSchoolRole.school_id == School.id)
        .where(UserSchoolRole.user_id == user.id, School.deleted_at.is_(None))
        .options(joinedload(School.members).joinedload(UserSchoolRole.user))
        .order_by(School.id)
    )
    return list(db.execute(query).unique().scalars().all())


def create_school(db: Session, payload: SchoolCreate, creator_user_id: int) -> School:
    existing_slug = db.execute(select(School).where(School.slug == payload.slug)).scalar_one_or_none()
    if existing_slug is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="School slug already exists")

    school = School(name=payload.name, slug=payload.slug, is_active=payload.is_active)
    db.add(school)
    db.flush()
    _replace_memberships(db=db, school=school, members_payload=payload.members)
    creator_is_member = db.execute(
        select(UserSchoolRole).where(UserSchoolRole.user_id == creator_user_id, UserSchoolRole.school_id == school.id)
    ).scalar_one_or_none()
    if creator_is_member is None:
        db.add(UserSchoolRole(user_id=creator_user_id, school_id=school.id, role=UserRole.admin.value))
    db.commit()
    db.refresh(school)
    return get_school_by_id(db=db, school_id=school.id)  # type: ignore[return-value]


def update_school(db: Session, school: School, payload: SchoolUpdate) -> School:
    if payload.slug is not None and payload.slug != school.slug:
        existing_slug = db.execute(select(School).where(School.slug == payload.slug)).scalar_one_or_none()
        if existing_slug is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="School slug already exists")
        school.slug = payload.slug
    if payload.name is not None:
        school.name = payload.name
    if payload.is_active is not None:
        school.is_active = payload.is_active
    if payload.members is not None:
        _replace_memberships(db=db, school=school, members_payload=payload.members)

    db.commit()
    db.refresh(school)
    return get_school_by_id(db=db, school_id=school.id)  # type: ignore[return-value]


def delete_school(db: Session, school: School) -> None:
    school.deleted_at = datetime.now(timezone.utc)
    school.is_active = False
    db.commit()


def add_user_school_role(db: Session, school_id: int, user_id: int, role: str) -> UserSchoolRole:
    school = db.execute(select(School).where(School.id == school_id, School.deleted_at.is_(None))).scalar_one_or_none()
    if school is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    user = db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.execute(
        select(UserSchoolRole).where(
            UserSchoolRole.school_id == school_id,
            UserSchoolRole.user_id == user_id,
            UserSchoolRole.role == role,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Membership already exists")

    membership = UserSchoolRole(school_id=school_id, user_id=user_id, role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def remove_user_school_roles(db: Session, school_id: int, user_id: int) -> None:
    memberships = db.execute(
        select(UserSchoolRole).where(UserSchoolRole.school_id == school_id, UserSchoolRole.user_id == user_id)
    ).scalars().all()
    if not memberships:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    for membership in memberships:
        db.delete(membership)
    db.commit()
