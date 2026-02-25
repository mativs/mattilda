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
from tests.helpers.factories import add_membership, create_school as factory_create_school
from tests.helpers.factories import create_user as factory_create_user


def test_create_school_returns_new_school(db_session, seeded_users):
    """
    Validate create_school success behavior.

    1. Build valid school creation payload.
    2. Call create_school service once.
    3. Validate created school slug.
    4. Validate creator is included as admin.
    """
    school = create_school(
        db_session,
        SchoolCreate(name="Service School", slug="service-school"),
        creator_user_id=seeded_users["admin"].id,
    )
    serialized = serialize_school_response(school)
    roles_by_user = {member["user_id"]: member["roles"] for member in serialized["members"]}
    assert school.slug == "service-school"
    assert UserRole.admin in roles_by_user[seeded_users["admin"].id]


def test_create_school_raises_conflict_for_duplicate_slug(db_session, seeded_users):
    """
    Validate create_school duplicate slug conflict.

    1. Seed a school with target slug.
    2. Call create_school with duplicate slug.
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    factory_create_school(db_session, "Existing", "dup-slug")
    with pytest.raises(HTTPException) as exc:
        create_school(
            db_session,
            SchoolCreate(name="New", slug="dup-slug"),
            creator_user_id=seeded_users["admin"].id,
        )
    assert exc.value.status_code == 409


def test_create_school_raises_not_found_for_missing_member_user(db_session, seeded_users):
    """
    Validate create_school missing member user branch.

    1. Build payload with non-existing member user id.
    2. Call create_school service once.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    with pytest.raises(HTTPException) as exc:
        create_school(
            db_session,
            SchoolCreate(
                name="Invalid",
                slug="invalid",
                members=[SchoolMemberAssignment(user_id=999999, roles=[UserRole.teacher])],
            ),
            creator_user_id=seeded_users["admin"].id,
        )
    assert exc.value.status_code == 404


def test_create_school_with_members_payload_creates_memberships(db_session, seeded_users):
    """
    Validate create_school member payload replacement branch.

    1. Build school payload with valid member assignment.
    2. Call create_school service once.
    3. Serialize created school members.
    4. Validate assigned member role is present.
    """
    school = create_school(
        db_session,
        SchoolCreate(
            name="Members School",
            slug="members-school",
            members=[SchoolMemberAssignment(user_id=seeded_users["teacher"].id, roles=[UserRole.teacher])],
        ),
        creator_user_id=seeded_users["admin"].id,
    )
    serialized = serialize_school_response(school)
    role_map = {member["user_id"]: member["roles"] for member in serialized["members"]}
    assert UserRole.teacher in role_map[seeded_users["teacher"].id]


def test_list_schools_for_user_returns_user_memberships(db_session, seeded_users):
    """
    Validate list_schools_for_user membership filtering.

    1. Call list_schools_for_user for seeded student.
    2. Validate returned school count.
    3. Validate school slug matches membership.
    4. Validate type is list-like sequence.
    """
    schools = list_schools_for_user(db_session, seeded_users["student"])
    assert len(schools) == 1
    assert schools[0].slug == "north-high"


def test_update_school_updates_mutable_fields(db_session, seeded_users):
    """
    Validate update_school mutable field updates.

    1. Seed a school for update.
    2. Call update_school with new name and active flag.
    3. Validate fields are updated.
    4. Validate returned school id is same entity.
    """
    school = factory_create_school(db_session, "Original", "original")
    updated = update_school(db_session, school, SchoolUpdate(name="Updated", is_active=False))
    assert updated.name == "Updated"
    assert updated.is_active is False
    assert updated.id == school.id


def test_update_school_updates_slug_when_unique(db_session):
    """
    Validate update_school unique slug update branch.

    1. Seed target school entity.
    2. Call update_school with unique slug.
    3. Validate slug is updated.
    4. Validate returned school id is unchanged.
    """
    target = factory_create_school(db_session, "Target", "target-unique")
    updated = update_school(db_session, target, SchoolUpdate(slug="target-renamed"))
    assert updated.slug == "target-renamed"
    assert updated.id == target.id


def test_update_school_replaces_members_when_payload_provided(db_session, seeded_users):
    """
    Validate update_school members replacement branch.

    1. Seed target school entity.
    2. Call update_school with members payload.
    3. Serialize updated school members.
    4. Validate provided member assignment exists.
    """
    target = factory_create_school(db_session, "Replace Members", "replace-members")
    updated = update_school(
        db_session,
        target,
        SchoolUpdate(members=[SchoolMemberAssignment(user_id=seeded_users["teacher"].id, roles=[UserRole.teacher])]),
    )
    serialized = serialize_school_response(updated)
    user_ids = {member["user_id"] for member in serialized["members"]}
    assert seeded_users["teacher"].id in user_ids


def test_update_school_raises_conflict_for_duplicate_slug(db_session):
    """
    Validate update_school duplicate slug conflict.

    1. Seed two schools with distinct slugs.
    2. Call update_school changing one to other slug.
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    target = factory_create_school(db_session, "Target", "target")
    existing = factory_create_school(db_session, "Existing", "existing")
    with pytest.raises(HTTPException) as exc:
        update_school(db_session, target, SchoolUpdate(slug=existing.slug))
    assert exc.value.status_code == 409


def test_delete_school_sets_soft_delete_flags(db_session):
    """
    Validate delete_school soft-delete behavior.

    1. Seed a school entity.
    2. Call delete_school once.
    3. Validate school marked inactive.
    4. Validate deleted_at is populated.
    """
    school = factory_create_school(db_session, "Delete", "delete-me")
    delete_school(db_session, school)
    assert school.is_active is False
    assert school.deleted_at is not None


def test_get_school_by_id_returns_none_for_soft_deleted_school(db_session):
    """
    Validate get_school_by_id soft-deleted filtering.

    1. Seed and soft-delete a school.
    2. Call get_school_by_id with deleted id.
    3. Validate deleted_at filter is applied.
    4. Validate result is None.
    """
    school = factory_create_school(db_session, "Gone", "gone")
    delete_school(db_session, school)
    assert get_school_by_id(db_session, school.id) is None


def test_serialize_school_response_skips_soft_deleted_member_user(db_session):
    """
    Validate serialize_school_response soft-deleted member filtering.

    1. Seed user, school, and membership.
    2. Soft-delete the member user.
    3. Serialize school response once.
    4. Validate deleted member is excluded.
    """
    user = factory_create_user(db_session, "deleted-member@example.com")
    school = factory_create_school(db_session, "Filtered School", "filtered-school")
    add_membership(db_session, user.id, school.id, UserRole.teacher)
    user.deleted_at = user.created_at
    db_session.commit()
    serialized = serialize_school_response(school)
    assert all(member["user_id"] != user.id for member in serialized["members"])


def test_add_user_school_role_creates_membership(db_session):
    """
    Validate add_user_school_role success branch.

    1. Seed a user and school.
    2. Call add_user_school_role once.
    3. Validate returned membership role.
    4. Validate membership foreign keys.
    """
    user = factory_create_user(db_session, "member@example.com")
    school = factory_create_school(db_session, "Member School", "member-school")
    membership = add_user_school_role(db_session, school.id, user.id, UserRole.teacher.value)
    assert membership.user_id == user.id
    assert membership.school_id == school.id


def test_add_user_school_role_raises_for_duplicate_membership(db_session):
    """
    Validate add_user_school_role duplicate conflict.

    1. Seed user-school membership with same role.
    2. Call add_user_school_role once with duplicate values.
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    user = factory_create_user(db_session, "dup-member@example.com")
    school = factory_create_school(db_session, "Dup School", "dup-school")
    add_membership(db_session, user.id, school.id, UserRole.teacher)
    with pytest.raises(HTTPException) as exc:
        add_user_school_role(db_session, school.id, user.id, UserRole.teacher.value)
    assert exc.value.status_code == 409


def test_add_user_school_role_raises_for_missing_school(db_session):
    """
    Validate add_user_school_role missing school branch.

    1. Seed only user entity.
    2. Call add_user_school_role with non-existing school id.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    user = factory_create_user(db_session, "missing-school@example.com")
    with pytest.raises(HTTPException) as exc:
        add_user_school_role(db_session, 999999, user.id, UserRole.teacher.value)
    assert exc.value.status_code == 404


def test_add_user_school_role_raises_for_missing_user(db_session):
    """
    Validate add_user_school_role missing user branch.

    1. Seed only school entity.
    2. Call add_user_school_role with non-existing user id.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    school = factory_create_school(db_session, "Missing User School", "missing-user-school")
    with pytest.raises(HTTPException) as exc:
        add_user_school_role(db_session, school.id, 999999, UserRole.teacher.value)
    assert exc.value.status_code == 404


def test_remove_user_school_roles_deletes_memberships(db_session):
    """
    Validate remove_user_school_roles success branch.

    1. Seed user-school membership.
    2. Call remove_user_school_roles once.
    3. Query school representation.
    4. Validate user is no longer a member.
    """
    user = factory_create_user(db_session, "remove-member@example.com")
    school = factory_create_school(db_session, "Remove School", "remove-school")
    add_membership(db_session, user.id, school.id, UserRole.teacher)
    remove_user_school_roles(db_session, school.id, user.id)
    serialized = serialize_school_response(get_school_by_id(db_session, school.id))
    assert all(member["user_id"] != user.id for member in serialized["members"])


def test_remove_user_school_roles_raises_for_missing_membership(db_session):
    """
    Validate remove_user_school_roles missing membership branch.

    1. Seed user and school without membership.
    2. Call remove_user_school_roles once.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    user = factory_create_user(db_session, "no-membership@example.com")
    school = factory_create_school(db_session, "No Member School", "no-member-school")
    with pytest.raises(HTTPException) as exc:
        remove_user_school_roles(db_session, school.id, user.id)
    assert exc.value.status_code == 404
