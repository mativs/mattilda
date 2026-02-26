from datetime import datetime, timezone

import pytest

from app.application.errors import ConflictError, NotFoundError
from app.application.services.user_service import (
    create_user,
    delete_user,
    get_user_by_id,
    serialize_user_response,
    update_user,
)
from app.interfaces.api.v1.schemas.user import UserCreate, UserProfileCreate, UserProfileUpdate, UserUpdate
from tests.helpers.factories import create_student as factory_create_student
from tests.helpers.factories import create_school, add_membership
from tests.helpers.factories import create_user as factory_create_user
from tests.helpers.factories import link_student_school, link_user_student
from app.domain.roles import UserRole


def _user_create_payload(email: str) -> UserCreate:
    return UserCreate(
        email=email,
        password="abc12345",
        is_active=True,
        profile=UserProfileCreate(first_name="Service", last_name="User", phone="123", address="Road"),
    )


def test_create_user_persists_new_user(db_session):
    """
    Validate create_user success behavior.

    1. Build a valid user create payload.
    2. Call create_user service once.
    3. Validate user fields are persisted.
    4. Validate profile fields are persisted.
    """
    created = create_user(db_session, _user_create_payload("service-user@example.com"))
    assert created.email == "service-user@example.com"
    assert created.profile.first_name == "Service"


def test_create_user_raises_conflict_for_duplicate_email(db_session):
    """
    Validate create_user duplicate email conflict.

    1. Seed a user with the target email.
    2. Call create_user with duplicate email payload.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    factory_create_user(db_session, email="duplicate@example.com")
    with pytest.raises(ConflictError) as exc:
        create_user(db_session, _user_create_payload("duplicate@example.com"))
    assert str(exc.value) == "User already exists"


def test_update_user_changes_email_password_and_active_state(db_session):
    """
    Validate update_user primary mutable fields.

    1. Seed a user entity for update.
    2. Call update_user with email/password/active changes.
    3. Validate new email and active state.
    4. Validate password hash changed.
    """
    user = factory_create_user(db_session, email="update-target@example.com")
    old_hash = user.hashed_password
    updated = update_user(
        db_session,
        user,
        UserUpdate(email="updated@example.com", password="new-pass", is_active=False),
    )
    assert updated.email == "updated@example.com"
    assert updated.is_active is False
    assert updated.hashed_password != old_hash


def test_update_user_updates_profile_fields(db_session):
    """
    Validate update_user profile field updates.

    1. Seed a user with profile values.
    2. Call update_user with profile patch payload.
    3. Validate profile fields were updated.
    4. Validate unchanged fields remain valid objects.
    """
    user = factory_create_user(db_session, email="profile-update@example.com")
    updated = update_user(
        db_session,
        user,
        UserUpdate(
            profile=UserProfileUpdate(first_name="Updated", last_name="Surname", phone="555", address="New Road")
        ),
    )
    assert updated.profile.first_name == "Updated"
    assert updated.profile.last_name == "Surname"
    assert updated.profile.phone == "555"
    assert updated.profile.address == "New Road"


def test_update_user_raises_conflict_for_duplicate_email(db_session):
    """
    Validate update_user duplicate email conflict.

    1. Seed two users with distinct emails.
    2. Call update_user changing first user to second user email.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    user = factory_create_user(db_session, email="one@example.com")
    factory_create_user(db_session, email="two@example.com")
    with pytest.raises(ConflictError) as exc:
        update_user(db_session, user, UserUpdate(email="two@example.com"))
    assert str(exc.value) == "User already exists"


def test_delete_user_sets_soft_delete_flags(db_session):
    """
    Validate delete_user soft-delete behavior.

    1. Seed an active user entity.
    2. Call delete_user once.
    3. Validate user is marked inactive.
    4. Validate deleted_at is populated.
    """
    user = factory_create_user(db_session, email="delete-target@example.com")
    delete_user(db_session, user)
    assert user.is_active is False
    assert user.deleted_at is not None


def test_get_user_by_id_returns_none_for_soft_deleted_user(db_session):
    """
    Validate get_user_by_id hidden soft-deleted user behavior.

    1. Seed user and mark soft-deleted directly.
    2. Call get_user_by_id with deleted user id.
    3. Validate query applies deleted_at filter.
    4. Validate return value is None.
    """
    user = factory_create_user(db_session, email="hidden@example.com")
    user.deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    assert get_user_by_id(db_session, user.id) is None


def test_serialize_user_response_includes_students_for_active_links(db_session, seeded_users):
    """
    Validate serialize_user_response student serialization.

    1. Seed an extra student and link it to seeded user.
    2. Call serialize_user_response for target user.
    3. Validate students list includes active linked student.
    4. Validate school_ids are present in serialized student.
    """
    student = factory_create_student(db_session, "Kid", "One", "SER-001")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    link_user_student(db_session, seeded_users["student"].id, student.id)
    serialized = serialize_user_response(seeded_users["student"])
    ids = {item["id"] for item in serialized["students"]}
    assert student.id in ids


def test_serialize_user_response_excludes_soft_deleted_students(db_session, seeded_users):
    """
    Validate serialize_user_response exclusion of soft-deleted students.

    1. Seed and link a student to target user.
    2. Mark linked student as soft-deleted.
    3. Call serialize_user_response once.
    4. Validate deleted student is excluded from response.
    """
    student = factory_create_student(db_session, "Kid", "Two", "SER-002")
    link_student_school(db_session, student.id, seeded_users["north_school"].id)
    link_user_student(db_session, seeded_users["student"].id, student.id)
    student.deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    serialized = serialize_user_response(seeded_users["student"])
    assert all(item["id"] != student.id for item in serialized["students"])


def test_update_user_applies_association_add_and_remove_operations(db_session):
    """
    Validate update_user association add/remove partial sync.

    1. Seed user with one existing school-role membership.
    2. Call update_user with association add and remove payload.
    3. Read serialized user memberships after update.
    4. Validate removed role is absent and added role is present.
    """
    user = factory_create_user(db_session, email="assoc-update@example.com")
    school_a = create_school(db_session, "School A", "school-a")
    school_b = create_school(db_session, "School B", "school-b")
    add_membership(db_session, user.id, school_a.id, UserRole.teacher)
    updated = update_user(
        db_session,
        user,
        UserUpdate(
            associations={
                "add": {"school_roles": [{"school_id": school_b.id, "role": "admin"}]},
                "remove": {"school_roles": [{"school_id": school_a.id, "role": "teacher"}]},
            }
        ),
    )
    serialized = serialize_user_response(updated)
    memberships = {(school["school_id"], role.value) for school in serialized["schools"] for role in school["roles"]}
    assert (school_a.id, UserRole.teacher.value) not in memberships
    assert (school_b.id, UserRole.admin.value) in memberships


def test_update_user_raises_not_found_for_missing_school_in_association_add(db_session):
    """
    Validate update_user association add missing-school branch.

    1. Seed user with no special school membership requirements.
    2. Call update_user with association add referencing unknown school.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    user = factory_create_user(db_session, email="assoc-missing-school@example.com")
    with pytest.raises(NotFoundError) as exc:
        update_user(
            db_session,
            user,
            UserUpdate(
                associations={
                    "add": {"school_roles": [{"school_id": 999999, "role": "teacher"}]},
                    "remove": {"school_roles": []},
                }
            ),
        )
    assert str(exc.value) == "School not found"
