from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.application.services.security_service import decode_access_token
from app.domain.roles import UserRole
from app.infrastructure.db.models import School, User, UserSchoolRole
from app.infrastructure.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    db.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), {"user_id": str(user.id)})
    return user


def require_authenticated(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def get_current_school_id(x_school_id: str | None = Header(default=None, alias="X-School-Id")) -> int:
    if x_school_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-School-Id header")
    try:
        return int(x_school_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-School-Id must be an integer") from exc


def get_current_school(
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
) -> School:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    db.execute(text("SELECT set_config('app.current_school_id', :school_id, true)"), {"school_id": str(school.id)})
    return school


def get_current_school_memberships(
    current_user: User = Depends(get_current_user),
    school: School = Depends(get_current_school),
    db: Session = Depends(get_db),
) -> list[UserSchoolRole]:
    memberships = (
        db.execute(
            select(UserSchoolRole).where(
                UserSchoolRole.user_id == current_user.id,
                UserSchoolRole.school_id == school.id,
            )
        )
        .scalars()
        .all()
    )
    if not memberships:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no access to this school")
    return memberships


def require_school_roles(allowed_roles: list[UserRole]) -> Callable:
    def checker(
        memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
        current_user: User = Depends(get_current_user),
    ) -> User:
        allowed = {role.value for role in allowed_roles}
        if not any(membership.role in allowed for membership in memberships):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient school permissions")
        return current_user

    return checker


def require_school_admin(current_user: User = Depends(require_school_roles([UserRole.admin]))) -> User:
    return current_user


def require_self_or_school_roles(user_id_param: str, allowed_roles: list[UserRole]) -> Callable:
    def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    ) -> User:
        allowed = {role.value for role in allowed_roles}
        if any(membership.role in allowed for membership in memberships):
            return current_user

        user_id_value = request.path_params.get(user_id_param)
        if user_id_value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user id parameter")

        if str(current_user.id) != str(user_id_value):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this user")
        return current_user

    return checker
