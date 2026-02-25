from datetime import datetime, timezone

import pytest

from app.application.errors import ConflictError, NotFoundError
from app.application.services.student_service import (
    associate_student_school,
    associate_user_student,
    create_student,
    create_student_for_school,
    deassociate_student_school,
    deassociate_user_student,
    delete_student,
    get_student_by_id,
    get_visible_student_for_user,
    list_students_for_school,
    list_students_for_user_in_school,
    serialize_student_response,
    update_student,
)
from app.interfaces.api.v1.schemas.student import StudentCreate, StudentUpdate
from tests.helpers.factories import create_school, create_student as factory_create_student
from tests.helpers.factories import create_user as factory_create_user
from tests.helpers.factories import link_student_school, link_user_student


def test_list_students_for_school_returns_students_in_school(db_session):
    """
    Validate list_students_for_school filtering behavior.

    1. Seed school and linked student.
    2. Call list_students_for_school once.
    3. Validate linked student is present.
    4. Validate returned collection is non-empty.
    """
    school = create_school(db_session, "North", "north")
    student = factory_create_student(db_session, "Kid", "One", "LST-001")
    link_student_school(db_session, student.id, school.id)
    students = list_students_for_school(db_session, school.id)
    assert any(item.id == student.id for item in students)


def test_list_students_for_user_in_school_returns_only_linked_students(db_session):
    """
    Validate list_students_for_user_in_school linkage filtering.

    1. Seed user, school, and linked student.
    2. Call list_students_for_user_in_school once.
    3. Validate linked student is present.
    4. Validate unrelated students are absent.
    """
    user = factory_create_user(db_session, "parent@example.com")
    school = create_school(db_session, "North", "north")
    student = factory_create_student(db_session, "Kid", "Two", "LST-002")
    link_student_school(db_session, student.id, school.id)
    link_user_student(db_session, user.id, student.id)
    students = list_students_for_user_in_school(db_session, user.id, school.id)
    assert any(item.id == student.id for item in students)


def test_create_student_persists_student(db_session):
    """
    Validate create_student success behavior.

    1. Build create payload with external id.
    2. Call create_student once.
    3. Validate student names are persisted.
    4. Validate external id is persisted.
    """
    student = create_student(db_session, StudentCreate(first_name="Mini", last_name="Kid", external_id="CRT-001"))
    assert student.first_name == "Mini"
    assert student.external_id == "CRT-001"


def test_create_student_raises_conflict_for_duplicate_external_id(db_session):
    """
    Validate create_student duplicate external id conflict.

    1. Seed student with external id.
    2. Call create_student with same external id.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    factory_create_student(db_session, "Dup", "Kid", "CRT-002")
    with pytest.raises(ConflictError) as exc:
        create_student(db_session, StudentCreate(first_name="Other", last_name="Kid", external_id="CRT-002"))
    assert str(exc.value) == "Student external_id already exists"


def test_create_student_for_school_creates_student_and_link(db_session):
    """
    Validate create_student_for_school success behavior.

    1. Seed target school.
    2. Call create_student_for_school once.
    3. Validate student was created.
    4. Validate student is visible in school listing.
    """
    school = create_school(db_session, "Link School", "link-school")
    student = create_student_for_school(
        db_session,
        StudentCreate(first_name="Linked", last_name="Kid", external_id="CRT-003"),
        school.id,
    )
    school_students = list_students_for_school(db_session, school.id)
    assert any(item.id == student.id for item in school_students)


def test_create_student_for_school_raises_for_missing_school(db_session):
    """
    Validate create_student_for_school missing school branch.

    1. Build valid create payload.
    2. Call create_student_for_school with unknown school id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    with pytest.raises(NotFoundError) as exc:
        create_student_for_school(
            db_session,
            StudentCreate(first_name="Ghost", last_name="Kid", external_id="CRT-004"),
            999999,
        )
    assert str(exc.value) == "School not found"


def test_update_student_updates_fields(db_session):
    """
    Validate update_student success behavior.

    1. Seed student entity.
    2. Call update_student with new values.
    3. Validate names are updated.
    4. Validate external id is updated.
    """
    student = factory_create_student(db_session, "Old", "Name", "UPD-001")
    updated = update_student(
        db_session,
        student,
        StudentUpdate(first_name="New", last_name="Name", external_id="UPD-002"),
    )
    assert updated.first_name == "New"
    assert updated.external_id == "UPD-002"


def test_update_student_raises_conflict_for_duplicate_external_id(db_session):
    """
    Validate update_student duplicate external id conflict.

    1. Seed two students with different external ids.
    2. Call update_student to duplicate second external id.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    target = factory_create_student(db_session, "One", "Kid", "UPD-010")
    other = factory_create_student(db_session, "Two", "Kid", "UPD-011")
    with pytest.raises(ConflictError) as exc:
        update_student(db_session, target, StudentUpdate(external_id=other.external_id))
    assert str(exc.value) == "Student external_id already exists"


def test_delete_student_sets_soft_delete_flag(db_session):
    """
    Validate delete_student soft-delete behavior.

    1. Seed student entity.
    2. Call delete_student once.
    3. Query deleted student by id helper.
    4. Validate deleted student is not returned.
    """
    student = factory_create_student(db_session, "Delete", "Kid", "DEL-001")
    delete_student(db_session, student)
    assert get_student_by_id(db_session, student.id) is None


def test_associate_user_student_creates_link(db_session):
    """
    Validate associate_user_student success behavior.

    1. Seed user and student entities.
    2. Call associate_user_student once.
    3. Validate returned link foreign keys.
    4. Validate link object is persisted.
    """
    user = factory_create_user(db_session, "assoc-user@example.com")
    student = factory_create_student(db_session, "Assoc", "Kid", "ASC-001")
    link = associate_user_student(db_session, user.id, student.id)
    assert link.user_id == user.id
    assert link.student_id == student.id


def test_associate_user_student_raises_for_duplicate_link(db_session):
    """
    Validate associate_user_student duplicate association.

    1. Seed user-student link directly.
    2. Call associate_user_student with same identifiers.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    user = factory_create_user(db_session, "dup-user-link@example.com")
    student = factory_create_student(db_session, "Dup", "Kid", "ASC-002")
    link_user_student(db_session, user.id, student.id)
    with pytest.raises(ConflictError) as exc:
        associate_user_student(db_session, user.id, student.id)
    assert str(exc.value) == "Association already exists"


def test_associate_user_student_raises_for_missing_user(db_session):
    """
    Validate associate_user_student missing user branch.

    1. Seed only student entity.
    2. Call associate_user_student with missing user id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    student = factory_create_student(db_session, "Missing", "User", "ASC-003")
    with pytest.raises(NotFoundError) as exc:
        associate_user_student(db_session, 999999, student.id)
    assert str(exc.value) == "User not found"


def test_associate_user_student_raises_for_missing_student(db_session):
    """
    Validate associate_user_student missing student branch.

    1. Seed only user entity.
    2. Call associate_user_student with missing student id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    user = factory_create_user(db_session, "missing-student@example.com")
    with pytest.raises(NotFoundError) as exc:
        associate_user_student(db_session, user.id, 999999)
    assert str(exc.value) == "Student not found"


def test_deassociate_user_student_deletes_link(db_session):
    """
    Validate deassociate_user_student success behavior.

    1. Seed user-student link.
    2. Call deassociate_user_student once.
    3. Call user-scoped list for that user/school.
    4. Validate removed student is absent.
    """
    user = factory_create_user(db_session, "deassoc-user@example.com")
    school = create_school(db_session, "School", "school")
    student = factory_create_student(db_session, "De", "Assoc", "ASC-100")
    link_student_school(db_session, student.id, school.id)
    link_user_student(db_session, user.id, student.id)
    deassociate_user_student(db_session, user.id, student.id)
    students = list_students_for_user_in_school(db_session, user.id, school.id)
    assert all(item.id != student.id for item in students)


def test_deassociate_user_student_raises_for_missing_link(db_session):
    """
    Validate deassociate_user_student missing association.

    1. Seed user and student without association.
    2. Call deassociate_user_student once.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    user = factory_create_user(db_session, "missing-link@example.com")
    student = factory_create_student(db_session, "Missing", "Link", "ASC-101")
    with pytest.raises(NotFoundError) as exc:
        deassociate_user_student(db_session, user.id, student.id)
    assert str(exc.value) == "Association not found"


def test_associate_student_school_creates_link(db_session):
    """
    Validate associate_student_school success behavior.

    1. Seed student and school entities.
    2. Call associate_student_school once.
    3. Validate returned link foreign keys.
    4. Validate link object is persisted.
    """
    school = create_school(db_session, "Assoc School", "assoc-school")
    student = factory_create_student(db_session, "School", "Kid", "SCH-001")
    link = associate_student_school(db_session, student.id, school.id)
    assert link.school_id == school.id
    assert link.student_id == student.id


def test_associate_student_school_raises_for_duplicate_link(db_session):
    """
    Validate associate_student_school duplicate association.

    1. Seed student-school link directly.
    2. Call associate_student_school with same identifiers.
    3. Validate service raises ConflictError.
    4. Validate exception message matches expected conflict.
    """
    school = create_school(db_session, "Dup School", "dup-school")
    student = factory_create_student(db_session, "Dup", "School", "SCH-002")
    link_student_school(db_session, student.id, school.id)
    with pytest.raises(ConflictError) as exc:
        associate_student_school(db_session, student.id, school.id)
    assert str(exc.value) == "Association already exists"


def test_associate_student_school_raises_for_missing_school(db_session):
    """
    Validate associate_student_school missing school branch.

    1. Seed only student entity.
    2. Call associate_student_school with missing school id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    student = factory_create_student(db_session, "Missing", "School", "SCH-003")
    with pytest.raises(NotFoundError) as exc:
        associate_student_school(db_session, student.id, 999999)
    assert str(exc.value) == "School not found"


def test_associate_student_school_raises_for_missing_student(db_session):
    """
    Validate associate_student_school missing student branch.

    1. Seed only school entity.
    2. Call associate_student_school with missing student id.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "Missing Student School", "missing-student-school")
    with pytest.raises(NotFoundError) as exc:
        associate_student_school(db_session, 999999, school.id)
    assert str(exc.value) == "Student not found"


def test_deassociate_student_school_deletes_link(db_session):
    """
    Validate deassociate_student_school success behavior.

    1. Seed student-school link.
    2. Call deassociate_student_school once.
    3. Call school-scoped list for that school.
    4. Validate removed student is absent.
    """
    school = create_school(db_session, "Deassoc School", "deassoc-school")
    student = factory_create_student(db_session, "De", "School", "SCH-100")
    link_student_school(db_session, student.id, school.id)
    deassociate_student_school(db_session, student.id, school.id)
    students = list_students_for_school(db_session, school.id)
    assert all(item.id != student.id for item in students)


def test_deassociate_student_school_raises_for_missing_link(db_session):
    """
    Validate deassociate_student_school missing association.

    1. Seed student and school without association.
    2. Call deassociate_student_school once.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    school = create_school(db_session, "No Link School", "no-link-school")
    student = factory_create_student(db_session, "No", "Link", "SCH-101")
    with pytest.raises(NotFoundError) as exc:
        deassociate_student_school(db_session, student.id, school.id)
    assert str(exc.value) == "Association not found"


def test_get_visible_student_for_user_returns_student_for_admin(db_session):
    """
    Validate get_visible_student_for_user admin visibility.

    1. Seed a school and linked student.
    2. Call get_visible_student_for_user with admin flag true.
    3. Validate helper returns a student object.
    4. Validate returned student id matches target.
    """
    user = factory_create_user(db_session, "admin-visible@example.com")
    school = create_school(db_session, "Admin School", "admin-school")
    student = factory_create_student(db_session, "Visible", "Admin", "VIS-ADM-001")
    link_student_school(db_session, student.id, school.id)
    visible = get_visible_student_for_user(db_session, student.id, school.id, user.id, is_admin=True)
    assert visible is not None
    assert visible.id == student.id


def test_get_visible_student_for_user_returns_none_for_non_associated_user(db_session):
    """
    Validate get_visible_student_for_user hidden student branch.

    1. Seed a school and linked student.
    2. Call get_visible_student_for_user with non-admin user not associated.
    3. Validate helper returns no result.
    4. Validate hidden student is not exposed.
    """
    user = factory_create_user(db_session, "hidden-student@example.com")
    school = create_school(db_session, "Hidden School", "hidden-school")
    student = factory_create_student(db_session, "Hidden", "Student", "VIS-HID-001")
    link_student_school(db_session, student.id, school.id)
    visible = get_visible_student_for_user(db_session, student.id, school.id, user.id, is_admin=False)
    assert visible is None


def test_serialize_student_response_includes_association_ids_and_refs(db_session):
    """
    Validate serialize_student_response includes user and school ids.

    1. Seed user, school, and student entities.
    2. Link student to user and school.
    3. Call serialize_student_response once.
    4. Validate serialized ids and reference payloads include linked entities.
    """
    user = factory_create_user(db_session, "serialize-student@example.com")
    school = create_school(db_session, "Serialize School", "serialize-school")
    student = factory_create_student(db_session, "Serialize", "Student", "SER-STU-001")
    link_student_school(db_session, student.id, school.id)
    link_user_student(db_session, user.id, student.id)
    serialized = serialize_student_response(student)
    assert user.id in serialized["user_ids"]
    assert school.id in serialized["school_ids"]
    assert any(item["id"] == user.id and item["email"] == user.email for item in serialized["users"])
    assert any(item["id"] == school.id and item["name"] == school.name for item in serialized["schools"])


def test_serialize_student_response_excludes_deleted_user_and_school_refs(db_session):
    """
    Validate serialize_student_response skips deleted linked references.

    1. Seed user, school, and student with active links.
    2. Mark linked user and school as soft-deleted.
    3. Call serialize_student_response once.
    4. Validate deleted links are excluded from ids and refs.
    """
    user = factory_create_user(db_session, "serialize-deleted@example.com")
    school = create_school(db_session, "Deleted Serialize School", "deleted-serialize-school")
    student = factory_create_student(db_session, "Serialize", "Deleted", "SER-STU-002")
    link_student_school(db_session, student.id, school.id)
    link_user_student(db_session, user.id, student.id)
    user.deleted_at = datetime.now(timezone.utc)
    school.deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    serialized = serialize_student_response(student)
    assert user.id not in serialized["user_ids"]
    assert school.id not in serialized["school_ids"]
    assert all(item["id"] != user.id for item in serialized["users"])
    assert all(item["id"] != school.id for item in serialized["schools"])


def test_update_student_applies_association_add_and_remove_operations(db_session):
    """
    Validate update_student association add/remove partial sync.

    1. Seed student with existing user and school links.
    2. Call update_student with add/remove association payload.
    3. Serialize updated student response.
    4. Validate removed links are gone and added links are present.
    """
    student = factory_create_student(db_session, "Assoc", "Update", "ASSOC-UPD-001")
    old_user = factory_create_user(db_session, "old-user@example.com")
    new_user = factory_create_user(db_session, "new-user@example.com")
    old_school = create_school(db_session, "Old School", "old-school")
    new_school = create_school(db_session, "New School", "new-school")
    link_user_student(db_session, old_user.id, student.id)
    link_student_school(db_session, student.id, old_school.id)
    updated = update_student(
        db_session,
        student,
        StudentUpdate(
            associations={
                "add": {"user_ids": [new_user.id], "school_ids": [new_school.id]},
                "remove": {"user_ids": [old_user.id], "school_ids": [old_school.id]},
            }
        ),
    )
    serialized = serialize_student_response(updated)
    assert old_user.id not in serialized["user_ids"]
    assert new_user.id in serialized["user_ids"]
    assert old_school.id not in serialized["school_ids"]
    assert new_school.id in serialized["school_ids"]


def test_update_student_raises_not_found_for_missing_user_in_association_add(db_session):
    """
    Validate update_student association add missing-user branch.

    1. Seed student entity for update.
    2. Call update_student with unknown user id in add payload.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    student = factory_create_student(db_session, "Missing", "User", "ASSOC-MISS-USER-001")
    with pytest.raises(NotFoundError) as exc:
        update_student(
            db_session,
            student,
            StudentUpdate(
                associations={
                    "add": {"user_ids": [999999], "school_ids": []},
                    "remove": {"user_ids": [], "school_ids": []},
                }
            ),
        )
    assert str(exc.value) == "User not found"


def test_update_student_raises_not_found_for_missing_school_in_association_add(db_session):
    """
    Validate update_student association add missing-school branch.

    1. Seed student and one valid user for update payload.
    2. Call update_student with unknown school id in add payload.
    3. Validate service raises NotFoundError.
    4. Validate exception message matches expected not-found.
    """
    student = factory_create_student(db_session, "Missing", "School", "ASSOC-MISS-SCHOOL-001")
    user = factory_create_user(db_session, "missing-school-user@example.com")
    with pytest.raises(NotFoundError) as exc:
        update_student(
            db_session,
            student,
            StudentUpdate(
                associations={
                    "add": {"user_ids": [user.id], "school_ids": [999999]},
                    "remove": {"user_ids": [], "school_ids": []},
                }
            ),
        )
    assert str(exc.value) == "School not found"
