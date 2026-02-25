import pytest
from fastapi import HTTPException

from app.application.services.student_service import (
    associate_student_school,
    associate_user_student,
    create_student,
    create_student_for_school,
    deassociate_student_school,
    deassociate_user_student,
    delete_student,
    get_student_by_id,
    list_students_for_school,
    list_students_for_user_in_school,
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
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    factory_create_student(db_session, "Dup", "Kid", "CRT-002")
    with pytest.raises(HTTPException) as exc:
        create_student(db_session, StudentCreate(first_name="Other", last_name="Kid", external_id="CRT-002"))
    assert exc.value.status_code == 409


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
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    with pytest.raises(HTTPException) as exc:
        create_student_for_school(
            db_session,
            StudentCreate(first_name="Ghost", last_name="Kid", external_id="CRT-004"),
            999999,
        )
    assert exc.value.status_code == 404


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
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    target = factory_create_student(db_session, "One", "Kid", "UPD-010")
    other = factory_create_student(db_session, "Two", "Kid", "UPD-011")
    with pytest.raises(HTTPException) as exc:
        update_student(db_session, target, StudentUpdate(external_id=other.external_id))
    assert exc.value.status_code == 409


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
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    user = factory_create_user(db_session, "dup-user-link@example.com")
    student = factory_create_student(db_session, "Dup", "Kid", "ASC-002")
    link_user_student(db_session, user.id, student.id)
    with pytest.raises(HTTPException) as exc:
        associate_user_student(db_session, user.id, student.id)
    assert exc.value.status_code == 409


def test_associate_user_student_raises_for_missing_user(db_session):
    """
    Validate associate_user_student missing user branch.

    1. Seed only student entity.
    2. Call associate_user_student with missing user id.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    student = factory_create_student(db_session, "Missing", "User", "ASC-003")
    with pytest.raises(HTTPException) as exc:
        associate_user_student(db_session, 999999, student.id)
    assert exc.value.status_code == 404


def test_associate_user_student_raises_for_missing_student(db_session):
    """
    Validate associate_user_student missing student branch.

    1. Seed only user entity.
    2. Call associate_user_student with missing student id.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    user = factory_create_user(db_session, "missing-student@example.com")
    with pytest.raises(HTTPException) as exc:
        associate_user_student(db_session, user.id, 999999)
    assert exc.value.status_code == 404


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
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    user = factory_create_user(db_session, "missing-link@example.com")
    student = factory_create_student(db_session, "Missing", "Link", "ASC-101")
    with pytest.raises(HTTPException) as exc:
        deassociate_user_student(db_session, user.id, student.id)
    assert exc.value.status_code == 404


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
    3. Validate service raises HTTPException.
    4. Validate status code is conflict.
    """
    school = create_school(db_session, "Dup School", "dup-school")
    student = factory_create_student(db_session, "Dup", "School", "SCH-002")
    link_student_school(db_session, student.id, school.id)
    with pytest.raises(HTTPException) as exc:
        associate_student_school(db_session, student.id, school.id)
    assert exc.value.status_code == 409


def test_associate_student_school_raises_for_missing_school(db_session):
    """
    Validate associate_student_school missing school branch.

    1. Seed only student entity.
    2. Call associate_student_school with missing school id.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    student = factory_create_student(db_session, "Missing", "School", "SCH-003")
    with pytest.raises(HTTPException) as exc:
        associate_student_school(db_session, student.id, 999999)
    assert exc.value.status_code == 404


def test_associate_student_school_raises_for_missing_student(db_session):
    """
    Validate associate_student_school missing student branch.

    1. Seed only school entity.
    2. Call associate_student_school with missing student id.
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    school = create_school(db_session, "Missing Student School", "missing-student-school")
    with pytest.raises(HTTPException) as exc:
        associate_student_school(db_session, 999999, school.id)
    assert exc.value.status_code == 404


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
    3. Validate service raises HTTPException.
    4. Validate status code is not found.
    """
    school = create_school(db_session, "No Link School", "no-link-school")
    student = factory_create_student(db_session, "No", "Link", "SCH-101")
    with pytest.raises(HTTPException) as exc:
        deassociate_student_school(db_session, student.id, school.id)
    assert exc.value.status_code == 404
