import pytest
from fastapi import HTTPException
from jose import jwt

from app.application.services.security_service import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.domain.roles import UserRole
from app.interfaces.api.v1.dependencies.auth import get_current_school_id, require_school_roles, require_self_or_school_roles


def test_token_and_password_helpers():
    """
    Validate security helper primitives for token and password handling.

    1. Create valid and invalid tokens and decode them.
    2. Validate decoding failure paths for malformed and wrong payload tokens.
    3. Hash and verify a password against both valid and invalid values.
    4. Validate expected helper outputs for all branches.
    """
    token = create_access_token(42, expires_minutes=1)
    assert decode_access_token(token) == 42
    assert decode_access_token("bad-token") is None

    wrong_sub = jwt.encode({"sub": "abc"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(wrong_sub) is None

    missing_sub = jwt.encode({"exp": 9999999999}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(missing_sub) is None

    hashed = hash_password("abc123")
    assert verify_password("abc123", hashed) is True
    assert verify_password("zzz", hashed) is False


def test_authenticate_user_success_and_failures(db_session, seeded_users):
    """
    Validate user authentication decision branches.

    1. Authenticate a valid seeded user with the right password.
    2. Validate wrong password and unknown email return no user.
    3. Mark user inactive and validate authentication is denied.
    4. Validate all expected outcomes from authenticate_user.
    """
    user = authenticate_user(db_session, email="admin@example.com", password="admin123")
    assert user is not None
    assert user.id == seeded_users["admin"].id

    assert authenticate_user(db_session, email="admin@example.com", password="wrong") is None
    assert authenticate_user(db_session, email="missing@example.com", password="admin123") is None

    seeded_users["admin"].is_active = False
    db_session.commit()
    assert authenticate_user(db_session, email="admin@example.com", password="admin123") is None


def test_auth_dependency_edge_branches():
    """
    Validate dependency helper edge branches used by route authorization.

    1. Trigger missing path parameter branch for self-or-role checker.
    2. Trigger invalid school header parsing branch.
    3. Trigger and satisfy school-role checker branches.
    4. Validate self and privileged access branches for request path checks.
    """
    dependency = require_self_or_school_roles("missing", [UserRole.admin])

    class RequestStub:
        path_params: dict[str, str] = {}

    class CurrentUserStub:
        id = 1

    with pytest.raises(HTTPException) as exc:
        dependency(RequestStub(), CurrentUserStub(), [])
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as header_exc:
        get_current_school_id("abc")
    assert header_exc.value.status_code == 400

    school_dependency = require_school_roles([UserRole.teacher])

    class MembershipStub:
        role = UserRole.student.value

    with pytest.raises(HTTPException) as school_exc:
        school_dependency([MembershipStub()], CurrentUserStub())
    assert school_exc.value.status_code == 403

    class TeacherMembershipStub:
        role = UserRole.teacher.value

    assert school_dependency([TeacherMembershipStub()], CurrentUserStub()).id == 1

    class RequestSelfStub:
        path_params: dict[str, str] = {"target": "1"}

    assert require_self_or_school_roles("target", [UserRole.admin])(RequestSelfStub(), CurrentUserStub(), []).id == 1

    class RequestOtherStub:
        path_params: dict[str, str] = {"target": "2"}

    assert require_self_or_school_roles("target", [UserRole.teacher])(
        RequestOtherStub(),
        CurrentUserStub(),
        [TeacherMembershipStub()],
    ).id == 1
