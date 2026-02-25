from datetime import datetime, timedelta, timezone
from typing import Any, cast

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.infrastructure.db.models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def create_access_token(user_id: int, expires_minutes: int | None = None) -> str:
    lifetime = expires_minutes if expires_minutes is not None else settings.jwt_access_token_expire_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=lifetime)
    payload = {"sub": str(user_id), "exp": expires_at}
    return cast(str, jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> int | None:
    try:
        payload = cast(dict[str, Any], jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]))
        subject = payload.get("sub")
        if not subject:
            return None
        return int(subject)
    except (JWTError, ValueError):
        return None


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
