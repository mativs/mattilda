from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.application.services.security_service import decode_access_token
from app.domain.roles import UserRole
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_authenticated(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def require_roles(allowed_roles: list[UserRole]) -> Callable:
    def checker(current_user: User = Depends(get_current_user)) -> User:
        allowed = {role.value for role in allowed_roles}
        if not any(role in allowed for role in current_user.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return checker


def require_self_or_roles(user_id_param: str, allowed_roles: list[UserRole]) -> Callable:
    def checker(request: Request, current_user: User = Depends(get_current_user)) -> User:
        allowed = {role.value for role in allowed_roles}
        if any(role in allowed for role in current_user.roles):
            return current_user

        user_id_value = request.path_params.get(user_id_param)
        if user_id_value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user id parameter")

        if str(current_user.id) != str(user_id_value):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this user")
        return current_user

    return checker
