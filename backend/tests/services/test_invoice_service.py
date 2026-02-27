from datetime import date, datetime, timezone

from app.application.services.invoice_service import (
    build_visible_invoices_query_for_student,
    get_visible_invoice_by_id,
    get_visible_invoice_items,
    get_visible_student_for_invoice_access,
    serialize_invoice_detail,
    serialize_invoice_summary,
)
from app.domain.invoice_status import InvoiceStatus
from tests.helpers.factories import (
    create_charge,
    create_invoice,
    create_invoice_item,
    create_school,
    create_student,
    create_user,
    list_from_query,
    link_student_school,
    link_user_student,
)


def test_get_visible_student_for_invoice_access_returns_student_for_admin(db_session):
    """
    Validate visible-student helper for admin users.

    1. Seed one school and one linked student.
    2. Call visible-student helper as admin.
    3. Validate helper returns a student object.
    4. Validate returned id matches seeded student.
    """
    school = create_school(db_session, "North Invoice", "north-invoice")
    student = create_student(db_session, "Alice", "Invoice", "INV-STU-001")
    admin = create_user(db_session, "admin-invoice@example.com")
    link_student_school(db_session, student.id, school.id)
    found = get_visible_student_for_invoice_access(
        db_session,
        student_id=student.id,
        school_id=school.id,
        user_id=admin.id,
        is_admin=True,
    )
    assert found is not None
    assert found.id == student.id


def test_get_visible_student_for_invoice_access_returns_none_for_hidden_non_admin(db_session):
    """
    Validate visible-student helper hides non-associated records.

    1. Seed one school with one linked student and one non-admin user.
    2. Call visible-student helper as non-admin without association.
    3. Validate helper returns no record.
    4. Validate hidden records are not exposed.
    """
    school = create_school(db_session, "North Hidden", "north-hidden")
    student = create_student(db_session, "Bob", "Hidden", "INV-STU-002")
    user = create_user(db_session, "teacher-invoice@example.com")
    link_student_school(db_session, student.id, school.id)
    found = get_visible_student_for_invoice_access(
        db_session,
        student_id=student.id,
        school_id=school.id,
        user_id=user.id,
        is_admin=False,
    )
    assert found is None


def test_build_visible_invoices_query_for_student_filters_non_admin_results(db_session):
    """
    Validate invoice list query scoping for non-admin users.

    1. Seed school, two students, and invoices for both students.
    2. Associate user with only one student.
    3. Execute non-admin visible invoices query once.
    4. Validate only associated-student invoices are returned.
    """
    school = create_school(db_session, "North Query", "north-query")
    student_a = create_student(db_session, "A", "One", "INV-STU-003")
    student_b = create_student(db_session, "B", "Two", "INV-STU-004")
    user = create_user(db_session, "user-query@example.com")
    link_student_school(db_session, student_a.id, school.id)
    link_student_school(db_session, student_b.id, school.id)
    link_user_student(db_session, user.id, student_a.id)
    create_invoice(
        db_session,
        school_id=school.id,
        student_id=student_a.id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        total_amount="100.00",
    )
    create_invoice(
        db_session,
        school_id=school.id,
        student_id=student_b.id,
        period="2026-03",
        issued_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        due_date=date(2026, 3, 10),
        total_amount="200.00",
    )
    query = build_visible_invoices_query_for_student(
        student_id=student_a.id,
        school_id=school.id,
        user_id=user.id,
        is_admin=False,
    )
    rows = list_from_query(db_session, query)
    assert len(rows) == 1
    assert rows[0].student_id == student_a.id


def test_get_visible_invoice_by_id_returns_invoice_with_items_for_admin(db_session):
    """
    Validate invoice-by-id helper with eager-loaded items.

    1. Seed school, student, invoice, charge, and one invoice item.
    2. Call invoice-by-id helper as admin.
    3. Validate helper returns invoice record.
    4. Validate returned invoice includes nested item relation.
    """
    school = create_school(db_session, "North Detail", "north-detail")
    student = create_student(db_session, "Detail", "Student", "INV-STU-005")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-04",
        issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        due_date=date(2026, 4, 10),
        total_amount="80.00",
    )
    charge = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Fee april",
        amount="80.00",
        due_date=date(2026, 4, 10),
    )
    create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=charge.id,
        description="Fee april",
        amount="80.00",
    )
    found = get_visible_invoice_by_id(
        db_session,
        invoice_id=invoice.id,
        school_id=school.id,
        user_id=9999,
        is_admin=True,
    )
    assert found is not None
    assert len(found.items) == 1


def test_get_visible_invoice_items_returns_none_for_hidden_invoice(db_session):
    """
    Validate invoice-items helper hidden-record behavior.

    1. Seed school, student, invoice, and non-admin user without association.
    2. Call invoice-items helper as non-admin.
    3. Validate helper returns None.
    4. Validate inaccessible invoices stay hidden.
    """
    school = create_school(db_session, "North Items", "north-items")
    student = create_student(db_session, "Items", "Student", "INV-STU-006")
    user = create_user(db_session, "hidden-items@example.com")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-05",
        issued_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        due_date=date(2026, 5, 10),
        total_amount="50.00",
        status=InvoiceStatus.closed,
    )
    items = get_visible_invoice_items(
        db_session,
        invoice_id=invoice.id,
        school_id=school.id,
        user_id=user.id,
        is_admin=False,
    )
    assert items is None


def test_serialize_invoice_summary_and_detail_include_expected_payload(db_session):
    """
    Validate invoice serializers produce expected shapes.

    1. Seed school, student, invoice, charge, and one invoice item.
    2. Build summary and detail payloads once.
    3. Validate summary has no nested items array.
    4. Validate detail includes nested invoice item snapshot fields.
    """
    school = create_school(db_session, "North Serialize", "north-serialize")
    student = create_student(db_session, "Serialize", "Student", "INV-STU-007")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-06",
        issued_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        due_date=date(2026, 6, 10),
        total_amount="120.00",
    )
    charge = create_charge(
        db_session,
        school_id=school.id,
        student_id=student.id,
        description="Monthly fee",
        amount="120.00",
        due_date=date(2026, 6, 10),
    )
    create_invoice_item(
        db_session,
        invoice_id=invoice.id,
        charge_id=charge.id,
        description="Monthly fee",
        amount="120.00",
    )
    found = get_visible_invoice_by_id(
        db_session,
        invoice_id=invoice.id,
        school_id=school.id,
        user_id=0,
        is_admin=True,
    )
    assert found is not None
    summary = serialize_invoice_summary(found)
    detail = serialize_invoice_detail(found)
    assert "items" not in summary
    assert detail["items"][0]["description"] == "Monthly fee"
