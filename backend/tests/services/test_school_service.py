import pytest
from fastapi import HTTPException

from app.application.services.school_service import (
    add_user_school_role,
    create_school,
    delete_school,
    get_school_by_id,
    list_schools_for_user,
    remove_user_school_roles,
    serialize_school_response,
    update_school,
)
from app.domain.roles import UserRole
from app.interfaces.api.v1.schemas.school import SchoolCreate, SchoolMemberAssignment, SchoolUpdate


def test_create_school_auto_assigns_creator_admin_and_handles_slug_conflict(db_session, seeded_users):
    """
    Validate school creation behavior and creator auto-admin assignment.

    1. Create a school with members through the service layer.
    2. Validate creator is automatically present with admin role.
    3. Validate duplicate school slug is rejected.
    4. Validate list for creator includes the new school.
    """
    payload = SchoolCreate(
        name="Service School",
        slug="service-school",
        members=[
            SchoolMemberAssignment(user_id=seeded_users["teacher"].id, roles=[UserRole.teacher]),
        ],
    )
    created = create_school(db_session, payload, creator_user_id=seeded_users["admin"].id)
    serialized = serialize_school_response(created)
    member_map = {member["user_id"]: member["roles"] for member in serialized["members"]}
    assert seeded_users["admin"].id in member_map
    assert UserRole.admin in member_map[seeded_users["admin"].id]

    with pytest.raises(HTTPException) as duplicate_slug:
        create_school(db_session, payload, creator_user_id=seeded_users["admin"].id)
    assert duplicate_slug.value.status_code == 409
    with pytest.raises(HTTPException) as missing_user:
        create_school(
            db_session,
            SchoolCreate(
                name="Invalid Members",
                slug="invalid-members-svc",
                members=[SchoolMemberAssignment(user_id=999999, roles=[UserRole.teacher])],
            ),
            creator_user_id=seeded_users["admin"].id,
        )
    assert missing_user.value.status_code == 404

    schools_for_admin = list_schools_for_user(db_session, seeded_users["admin"])
    assert any(school.slug == "service-school" for school in schools_for_admin)

    seeded_users["teacher"].deleted_at = seeded_users["admin"].created_at
    db_session.commit()
    serialized_after_teacher_delete = serialize_school_response(get_school_by_id(db_session, created.id))
    assert all(member["user_id"] != seeded_users["teacher"].id for member in serialized_after_teacher_delete["members"])


def test_update_delete_and_membership_helpers(db_session, seeded_users):
    """
    Validate school update, soft-delete, and membership helper behavior.

    1. Create and update a school with new member payload.
    2. Add and remove user-school roles through helper functions.
    3. Validate duplicate and missing membership error branches.
    4. Soft-delete the school and validate hidden lookup behavior.
    """
    created = create_school(
        db_session,
        SchoolCreate(name="Edit School", slug="edit-school"),
        creator_user_id=seeded_users["admin"].id,
    )

    updated = update_school(
        db_session,
        created,
        SchoolUpdate(
            name="Edited Name",
            slug="edited-school",
            is_active=False,
            members=[SchoolMemberAssignment(user_id=seeded_users["teacher"].id, roles=[UserRole.teacher])],
        ),
    )
    assert updated.name == "Edited Name"
    assert updated.slug == "edited-school"
    assert updated.is_active is False
    with pytest.raises(HTTPException) as duplicate_slug_update:
        update_school(db_session, updated, SchoolUpdate(slug=seeded_users["north_school"].slug))
    assert duplicate_slug_update.value.status_code == 409

    with pytest.raises(HTTPException) as duplicate_membership:
        add_user_school_role(
            db_session,
            school_id=seeded_users["north_school"].id,
            user_id=seeded_users["teacher"].id,
            role=UserRole.teacher.value,
        )
    assert duplicate_membership.value.status_code == 409

    with pytest.raises(HTTPException) as missing_school:
        add_user_school_role(
            db_session,
            school_id=999999,
            user_id=seeded_users["teacher"].id,
            role=UserRole.teacher.value,
        )
    assert missing_school.value.status_code == 404

    with pytest.raises(HTTPException) as missing_user:
        add_user_school_role(
            db_session,
            school_id=seeded_users["north_school"].id,
            user_id=999999,
            role=UserRole.teacher.value,
        )
    assert missing_user.value.status_code == 404

    remove_user_school_roles(
        db_session,
        school_id=seeded_users["north_school"].id,
        user_id=seeded_users["teacher"].id,
    )
    with pytest.raises(HTTPException) as missing_membership:
        remove_user_school_roles(
            db_session,
            school_id=seeded_users["north_school"].id,
            user_id=seeded_users["teacher"].id,
        )
    assert missing_membership.value.status_code == 404

    delete_school(db_session, created)
    assert created.deleted_at is not None
    assert get_school_by_id(db_session, created.id) is None

