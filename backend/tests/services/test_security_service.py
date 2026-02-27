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
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school_id,
    require_school_roles,
    require_self_or_school_roles,
)
from tests.helpers.factories import commit_session


def test_decode_access_token_returns_user_id_for_valid_token():
    """
    Validate decoding of a valid JWT token.

    1. Create a valid access token for a known user id.
    2. Decode the token via security helper.
    3. Validate returned subject matches the user id.
    4. Validate helper returns a non-null decoded id.
    """
    token = create_access_token(42, expires_minutes=1)
    assert decode_access_token(token) == 42


def test_decode_access_token_returns_none_for_malformed_token():
    """
    Validate malformed token handling in decode helper.

    1. Provide a malformed token string.
    2. Decode token via security helper.
    3. Validate decode path handles error internally.
    4. Validate function returns None.
    """
    assert decode_access_token("bad-token") is None


def test_decode_access_token_returns_none_for_non_integer_subject():
    """
    Validate non-integer subject handling in decode helper.

    1. Build JWT token with non-integer subject value.
    2. Decode token via security helper.
    3. Validate conversion failure path is handled.
    4. Validate function returns None.
    """
    wrong_sub = jwt.encode({"sub": "abc"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(wrong_sub) is None


def test_decode_access_token_returns_none_for_missing_subject():
    """
    Validate missing subject handling in decode helper.

    1. Build JWT token with expiration but no subject.
    2. Decode token via security helper.
    3. Validate missing subject branch is executed.
    4. Validate function returns None.
    """
    missing_sub = jwt.encode({"exp": 9999999999}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(missing_sub) is None


def test_hash_password_returns_verifiable_hash():
    """
    Validate password hashing helper output.

    1. Hash a known password with hash_password helper.
    2. Verify hashed value using verify_password helper.
    3. Validate hash verifies with the original password.
    4. Validate resulting hash is persisted as a string.
    """
    hashed = hash_password("abc123")
    assert verify_password("abc123", hashed) is True


def test_verify_password_returns_false_for_invalid_password():
    """
    Validate password verify failure branch.

    1. Hash a known valid password.
    2. Verify with a different invalid password.
    3. Validate verify helper returns failure.
    4. Validate boolean result is False.
    """
    hashed = hash_password("abc123")
    assert verify_password("zzz", hashed) is False


def test_authenticate_user_returns_user_when_credentials_are_valid(db_session, seeded_users):
    """
    Validate authenticate_user success branch.

    1. Use seeded active user with valid credentials.
    2. Call authenticate_user with matching email/password.
    3. Validate helper returns a user object.
    4. Validate returned user id matches seeded user.
    """
    user = authenticate_user(db_session, email="admin@example.com", password="admin123")
    assert user is not None
    assert user.id == seeded_users["admin"].id


def test_authenticate_user_returns_none_for_wrong_password(db_session):
    """
    Validate authenticate_user wrong-password branch.

    1. Use seeded active user email.
    2. Call authenticate_user with invalid password.
    3. Validate password verification fails.
    4. Validate helper returns None.
    """
    assert authenticate_user(db_session, email="admin@example.com", password="wrong") is None


def test_authenticate_user_returns_none_for_unknown_email(db_session):
    """
    Validate authenticate_user unknown-email branch.

    1. Use a non-existent email value.
    2. Call authenticate_user with arbitrary password.
    3. Validate no user is found in query.
    4. Validate helper returns None.
    """
    assert authenticate_user(db_session, email="missing@example.com", password="admin123") is None


def test_authenticate_user_returns_none_for_inactive_user(db_session, seeded_users):
    """
    Validate authenticate_user inactive-user branch.

    1. Mark seeded user as inactive in DB state.
    2. Call authenticate_user with valid credentials.
    3. Validate inactive check blocks authentication.
    4. Validate helper returns None.
    """
    seeded_users["admin"].is_active = False
    commit_session(db_session)
    assert authenticate_user(db_session, email="admin@example.com", password="admin123") is None


def test_require_self_or_school_roles_raises_when_path_param_missing():
    """
    Validate require_self_or_school_roles missing-path branch.

    1. Build dependency checker with missing path key.
    2. Invoke checker with request path params missing target.
    3. Validate dependency raises HTTPException.
    4. Validate error status code is 400.
    """
    dependency = require_self_or_school_roles("missing", [UserRole.admin])

    class RequestStub:
        path_params: dict[str, str] = {}

    class CurrentUserStub:
        id = 1

    with pytest.raises(HTTPException) as exc:
        dependency(RequestStub(), CurrentUserStub(), [])
    assert exc.value.status_code == 400


def test_get_current_school_id_raises_for_non_integer_header():
    """
    Validate school header parsing error branch.

    1. Call get_current_school_id with invalid string.
    2. Trigger integer cast failure.
    3. Validate dependency raises HTTPException.
    4. Validate error status code is 400.
    """
    with pytest.raises(HTTPException) as header_exc:
        get_current_school_id("abc")
    assert header_exc.value.status_code == 400


def test_require_school_roles_raises_for_disallowed_role():
    """
    Validate require_school_roles forbidden branch.

    1. Create checker allowing only teacher role.
    2. Invoke checker with membership containing student role.
    3. Validate dependency raises HTTPException.
    4. Validate error status code is 403.
    """
    school_dependency = require_school_roles([UserRole.teacher])

    class MembershipStub:
        role = UserRole.student.value

    class CurrentUserStub:
        id = 1

    with pytest.raises(HTTPException) as school_exc:
        school_dependency([MembershipStub()], CurrentUserStub())
    assert school_exc.value.status_code == 403


def test_require_school_roles_returns_user_for_allowed_role():
    """
    Validate require_school_roles success branch.

    1. Create checker allowing teacher role.
    2. Invoke checker with membership containing teacher role.
    3. Validate dependency returns current user.
    4. Validate returned user id value.
    """
    school_dependency = require_school_roles([UserRole.teacher])

    class TeacherMembershipStub:
        role = UserRole.teacher.value

    class CurrentUserStub:
        id = 1

    assert school_dependency([TeacherMembershipStub()], CurrentUserStub()).id == 1


def test_require_self_or_school_roles_returns_user_for_self_path_match():
    """
    Validate require_self_or_school_roles self-access branch.

    1. Build checker for target path param.
    2. Invoke checker with matching current user id.
    3. Validate self-access condition is satisfied.
    4. Validate returned user id value.
    """

    class RequestSelfStub:
        path_params: dict[str, str] = {"target": "1"}

    class CurrentUserStub:
        id = 1

    assert require_self_or_school_roles("target", [UserRole.admin])(RequestSelfStub(), CurrentUserStub(), []).id == 1


def test_require_self_or_school_roles_returns_user_for_allowed_membership():
    """
    Validate require_self_or_school_roles privileged-role branch.

    1. Build checker allowing teacher role.
    2. Invoke checker with non-matching target and teacher membership.
    3. Validate membership role bypasses self-check.
    4. Validate returned user id value.
    """

    class RequestOtherStub:
        path_params: dict[str, str] = {"target": "2"}

    class CurrentUserStub:
        id = 1

    class TeacherMembershipStub:
        role = UserRole.teacher.value

    assert (
        require_self_or_school_roles("target", [UserRole.teacher])(
            RequestOtherStub(),
            CurrentUserStub(),
            [TeacherMembershipStub()],
        ).id
        == 1
    )
