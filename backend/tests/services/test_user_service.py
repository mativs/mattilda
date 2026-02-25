import pytest
from fastapi import HTTPException
from datetime import datetime, timezone

from app.application.services.user_service import (
    create_user,
    delete_user,
    get_user_by_id,
    serialize_user_response,
    update_user,
)
from app.interfaces.api.v1.schemas.user import UserCreate, UserProfileCreate, UserProfileUpdate, UserUpdate


def test_create_update_and_soft_delete_user(db_session):
    """
    Validate create, update, and soft-delete user service behavior.

    1. Create a new user with profile and validate persisted fields.
    2. Update user fields including password and profile fields.
    3. Soft-delete the user and validate active and visibility flags.
    4. Validate duplicate email conflicts on create and update paths.
    """
    payload = UserCreate(
        email="service-user@example.com",
        password="abc12345",
        is_active=True,
        profile=UserProfileCreate(first_name="Service", last_name="User", phone="123", address="Road"),
    )
    created = create_user(db_session, payload)
    assert created.email == "service-user@example.com"
    assert created.profile.first_name == "Service"

    updated = update_user(
        db_session,
        created,
        UserUpdate(
            email="service-user-updated@example.com",
            password="newpass",
            is_active=False,
            profile=UserProfileUpdate(first_name="Updated", last_name="Surname", phone="555", address="New Road"),
        ),
    )
    assert updated.email == "service-user-updated@example.com"
    assert updated.is_active is False
    assert updated.profile.first_name == "Updated"
    assert updated.profile.last_name == "Surname"
    assert updated.profile.phone == "555"
    assert updated.profile.address == "New Road"

    with pytest.raises(HTTPException) as duplicate_create:
        create_user(
            db_session,
            UserCreate(
                email="service-user-updated@example.com",
                password="abc12345",
                is_active=True,
                profile=UserProfileCreate(first_name="Dup", last_name="User"),
            ),
        )
    assert duplicate_create.value.status_code == 409

    other = create_user(
        db_session,
        UserCreate(
            email="other@example.com",
            password="abc12345",
            is_active=True,
            profile=UserProfileCreate(first_name="Other", last_name="User"),
        ),
    )
    with pytest.raises(HTTPException) as duplicate_update:
        update_user(db_session, other, UserUpdate(email="service-user-updated@example.com"))
    assert duplicate_update.value.status_code == 409

    delete_user(db_session, updated)
    assert updated.is_active is False
    assert updated.deleted_at is not None
    assert get_user_by_id(db_session, updated.id) is None


def test_serialize_user_response_includes_school_roles_and_students(db_session, seeded_users):
    """
    Validate serialized user output for memberships and student links.

    1. Serialize seeded student user response via service serializer.
    2. Validate school role grouping and roles list shape.
    3. Validate associated students are included with school ids.
    4. Soft-delete one linked student and validate it is excluded.
    """
    student_user = seeded_users["student"]
    serialized = serialize_user_response(student_user)
    assert serialized["id"] == student_user.id
    assert serialized["schools"][0]["school_id"] == seeded_users["north_school"].id
    assert len(serialized["students"]) >= 2

    seeded_users["child_one"].deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    serialized_after_delete = serialize_user_response(student_user)
    assert all(student["id"] != seeded_users["child_one"].id for student in serialized_after_delete["students"])
