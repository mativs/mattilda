from app.application.errors import ValidationError
from app.application.services.school_invoice_generation_service import generate_invoices_for_school
from tests.helpers.factories import create_school, create_student, link_student_school


def test_generate_invoices_for_school_processes_all_students(db_session, monkeypatch):
    """
    Validate school-wide generation iterates through every active student in school.

    1. Seed one school with two linked active students.
    2. Mock per-student generation helper to record student ids.
    3. Call school-wide generation once.
    4. Validate both students were processed and reported as generated.
    """

    school = create_school(db_session, "Batch School", "batch-school")
    first_student = create_student(db_session, "First", "Kid", "BATCH-STU-001")
    second_student = create_student(db_session, "Second", "Kid", "BATCH-STU-002")
    link_student_school(db_session, first_student.id, school.id)
    link_student_school(db_session, second_student.id, school.id)

    processed: list[int] = []

    def _fake_generate_invoice_for_student(db, school_id, student_id, as_of=None):
        processed.append(student_id)
        return None

    monkeypatch.setattr(
        "app.application.services.school_invoice_generation_service.generate_invoice_for_student",
        _fake_generate_invoice_for_student,
    )
    payload = generate_invoices_for_school(db_session, school_id=school.id)
    assert sorted(processed) == sorted([first_student.id, second_student.id])
    assert payload["processed_students"] == 2
    assert payload["generated_students"] == 2
    assert payload["skipped_students"] == 0
    assert payload["failed_students"] == 0


def test_generate_invoices_for_school_tracks_skipped_and_failed_students(db_session, monkeypatch):
    """
    Validate school-wide generation classifies validation skips and generic failures.

    1. Seed one school with three linked students.
    2. Mock per-student generation helper to return success, validation error, and runtime error.
    3. Call school-wide generation once.
    4. Validate summary counts and error entries by type.
    """

    school = create_school(db_session, "Batch School Two", "batch-school-two")
    first_student = create_student(db_session, "Ok", "Kid", "BATCH-STU-003")
    second_student = create_student(db_session, "Skip", "Kid", "BATCH-STU-004")
    third_student = create_student(db_session, "Fail", "Kid", "BATCH-STU-005")
    link_student_school(db_session, first_student.id, school.id)
    link_student_school(db_session, second_student.id, school.id)
    link_student_school(db_session, third_student.id, school.id)

    def _fake_generate_invoice_for_student(db, school_id, student_id, as_of=None):
        if student_id == second_student.id:
            raise ValidationError("No unpaid charges available for invoice generation")
        if student_id == third_student.id:
            raise RuntimeError("unexpected error")
        return None

    monkeypatch.setattr(
        "app.application.services.school_invoice_generation_service.generate_invoice_for_student",
        _fake_generate_invoice_for_student,
    )
    payload = generate_invoices_for_school(db_session, school_id=school.id)
    assert payload["processed_students"] == 3
    assert payload["generated_students"] == 1
    assert payload["skipped_students"] == 1
    assert payload["failed_students"] == 1
    assert any(item["student_id"] == second_student.id and item["type"] == "skipped" for item in payload["errors"])
    assert any(item["student_id"] == third_student.id and item["type"] == "failed" for item in payload["errors"])
