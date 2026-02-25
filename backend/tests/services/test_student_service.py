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


def test_create_update_list_and_delete_student(db_session, seeded_users):
    """
    Validate primary student CRUD and listing behavior in service layer.

    1. Create a student linked to an active school and validate list visibility.
    2. Update student values and validate conflict branch for duplicate external id.
    3. Validate user-scoped listing only includes associated students.
    4. Soft-delete student and validate hidden lookup behavior.
    """
    student = create_student_for_school(
        db_session,
        StudentCreate(first_name="Mini", last_name="Kid", external_id="SVC-001"),
        school_id=seeded_users["north_school"].id,
    )
    assert student.id is not None
    assert any(item.id == student.id for item in list_students_for_school(db_session, seeded_users["north_school"].id))

    updated = update_student(
        db_session,
        student,
        StudentUpdate(first_name="Mini2", last_name="Kid2", external_id="SVC-002"),
    )
    assert updated.first_name == "Mini2"
    assert updated.external_id == "SVC-002"

    with pytest.raises(HTTPException) as external_conflict:
        update_student(db_session, updated, StudentUpdate(external_id=seeded_users["child_one"].external_id))
    assert external_conflict.value.status_code == 409

    assert not any(
        item.id == student.id
        for item in list_students_for_user_in_school(
            db_session,
            seeded_users["student"].id,
            seeded_users["north_school"].id,
        )
    )

    delete_student(db_session, updated)
    assert get_student_by_id(db_session, updated.id) is None


def test_student_association_helpers_and_error_branches(db_session, seeded_users):
    """
    Validate student association helper success and error branches.

    1. Create a base student for association operations.
    2. Validate duplicate and missing entity errors for user-student associations.
    3. Validate duplicate and missing entity errors for student-school associations.
    4. Validate deassociation not-found branches after successful removal.
    """
    base = create_student(db_session, StudentCreate(first_name="Assoc", last_name="Case", external_id="SVC-010"))

    with pytest.raises(HTTPException) as missing_school:
        create_student_for_school(
            db_session,
            StudentCreate(first_name="Ghost", last_name="Case", external_id="SVC-011"),
            school_id=999999,
        )
    assert missing_school.value.status_code == 404

    link_user = associate_user_student(db_session, seeded_users["student"].id, base.id)
    assert link_user.user_id == seeded_users["student"].id
    with pytest.raises(HTTPException) as duplicate_user_link:
        associate_user_student(db_session, seeded_users["student"].id, base.id)
    assert duplicate_user_link.value.status_code == 409
    with pytest.raises(HTTPException) as missing_user_link:
        associate_user_student(db_session, 999999, base.id)
    assert missing_user_link.value.status_code == 404
    with pytest.raises(HTTPException) as missing_student_link:
        associate_user_student(db_session, seeded_users["student"].id, 999999)
    assert missing_student_link.value.status_code == 404

    link_school = associate_student_school(db_session, base.id, seeded_users["north_school"].id)
    assert link_school.school_id == seeded_users["north_school"].id
    with pytest.raises(HTTPException) as duplicate_school_link:
        associate_student_school(db_session, base.id, seeded_users["north_school"].id)
    assert duplicate_school_link.value.status_code == 409
    with pytest.raises(HTTPException) as missing_school_link:
        associate_student_school(db_session, base.id, 999999)
    assert missing_school_link.value.status_code == 404
    with pytest.raises(HTTPException) as missing_student_school_link:
        associate_student_school(db_session, 999999, seeded_users["north_school"].id)
    assert missing_student_school_link.value.status_code == 404

    deassociate_user_student(db_session, seeded_users["student"].id, base.id)
    with pytest.raises(HTTPException) as missing_deassociate_user:
        deassociate_user_student(db_session, seeded_users["student"].id, base.id)
    assert missing_deassociate_user.value.status_code == 404

    deassociate_student_school(db_session, base.id, seeded_users["north_school"].id)
    with pytest.raises(HTTPException) as missing_deassociate_school:
        deassociate_student_school(db_session, base.id, seeded_users["north_school"].id)
    assert missing_deassociate_school.value.status_code == 404
