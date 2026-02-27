from datetime import date, datetime, timezone

import pytest

from app.application.errors import NotFoundError
from app.application.services.reconciliation_service import (
    create_queued_reconciliation_run,
    execute_reconciliation_run,
    get_reconciliation_run_with_findings,
    list_reconciliation_runs_query,
    mark_reconciliation_run_failed,
    run_school_reconciliation,
    serialize_reconciliation_finding,
    serialize_reconciliation_run,
)
from app.domain.invoice_status import InvoiceStatus
from tests.helpers.factories import create_invoice, create_payment, create_school, create_student, create_user, link_student_school


def test_run_school_reconciliation_persists_run_and_findings(db_session):
    """
    Validate full reconciliation orchestration persists run and findings.

    1. Seed school data that triggers at least one finding.
    2. Call run_school_reconciliation once.
    3. Reload run with findings.
    4. Validate completed status and non-empty findings.
    """

    school = create_school(db_session, "Recon Service", "recon-service")
    student = create_student(db_session, "R", "One", "REC-SRV-001")
    link_student_school(db_session, student.id, school.id)
    invoice = create_invoice(
        db_session,
        school_id=school.id,
        student_id=student.id,
        period="2026-07",
        issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        due_date=date(2026, 7, 10),
        total_amount="30.00",
        status=InvoiceStatus.open,
    )
    create_payment(
        db_session,
        school_id=school.id,
        student_id=student.id,
        invoice_id=invoice.id,
        amount="30.00",
        paid_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    run = run_school_reconciliation(db_session, school_id=school.id)
    refreshed = get_reconciliation_run_with_findings(db_session, school_id=school.id, run_id=run.id)
    assert refreshed.status == "completed"
    assert len(refreshed.findings) >= 1


def test_execute_reconciliation_run_raises_not_found_for_unknown_run(db_session):
    """
    Validate execute_reconciliation_run rejects unknown run id.

    1. Keep empty run table.
    2. Call execute_reconciliation_run with unknown id.
    3. Catch raised NotFoundError.
    4. Validate error message matches expected value.
    """

    with pytest.raises(NotFoundError) as exc:
        execute_reconciliation_run(db_session, run_id=999999)
    assert str(exc.value) == "Reconciliation run not found"


def test_create_queued_run_and_mark_failed_updates_state(db_session):
    """
    Validate queued run creation and failure marker transitions state.

    1. Seed school and user.
    2. Create queued run via helper.
    3. Mark run as failed with message.
    4. Validate status and summary_json error.
    """

    school = create_school(db_session, "Recon Queue", "recon-queue")
    user = create_user(db_session, "recon-failed@example.com")
    run = create_queued_reconciliation_run(db_session, school_id=school.id, triggered_by_user_id=user.id)
    mark_reconciliation_run_failed(db_session, run_id=run.id, error_message="boom")
    refreshed = get_reconciliation_run_with_findings(db_session, school_id=school.id, run_id=run.id)
    assert refreshed.status == "failed"
    assert refreshed.summary_json["error"] == "boom"


def test_mark_reconciliation_run_failed_ignores_unknown_run(db_session):
    """
    Validate failure marker no-ops for unknown run identifiers.

    1. Keep reconciliation run table empty.
    2. Call mark_reconciliation_run_failed with unknown id.
    3. Complete call without exception.
    4. Validate function remains safe for missing runs.
    """

    mark_reconciliation_run_failed(db_session, run_id=999999, error_message="not-found")


def test_get_reconciliation_run_with_findings_raises_not_found(db_session):
    """
    Validate detail helper raises not-found for absent run in school scope.

    1. Seed one school without reconciliation runs.
    2. Call run detail helper with unknown run id.
    3. Catch NotFoundError.
    4. Validate message matches expected value.
    """

    school = create_school(db_session, "Recon Missing Detail", "recon-missing-detail")
    with pytest.raises(NotFoundError) as exc:
        get_reconciliation_run_with_findings(db_session, school_id=school.id, run_id=999999)
    assert str(exc.value) == "Reconciliation run not found"


def test_serialize_helpers_and_list_query_return_expected_payloads(db_session):
    """
    Validate serialization helpers and list query output shape.

    1. Seed one school and queued reconciliation run.
    2. Execute list query and serialize run payload.
    3. Serialize one finding payload if present.
    4. Validate critical ids and status fields exist.
    """

    school = create_school(db_session, "Recon Serialize", "recon-serialize")
    run = create_queued_reconciliation_run(db_session, school_id=school.id)
    run_rows = list(db_session.execute(list_reconciliation_runs_query(school_id=school.id)).scalars().all())
    run_payload = serialize_reconciliation_run(run_rows[0])
    assert run_payload["id"] == run.id
    assert run_payload["status"] == "queued"
    if run_rows[0].findings:
        finding_payload = serialize_reconciliation_finding(run_rows[0].findings[0])
        assert finding_payload["run_id"] == run.id
