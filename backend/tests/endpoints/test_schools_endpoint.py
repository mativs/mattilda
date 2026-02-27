from datetime import date, datetime, timezone

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.domain.roles import UserRole
from app.infrastructure.db.models import ReconciliationFinding, ReconciliationRun
from tests.helpers.auth import auth_header, school_header, token_for_user
from tests.helpers.factories import (
    add_membership,
    create_charge,
    create_invoice,
    create_payment,
    create_school,
    persist_entity,
    refresh_entity,
)


def test_get_schools_returns_200_for_authenticated_user(client, seeded_users):
    """
    Validate schools list success for authenticated user.

    1. Build admin auth header.
    2. Call schools list endpoint once.
    3. Receive successful response.
    4. Validate payload uses paginated envelope.
    """
    response = client.get("/api/v1/schools", headers=auth_header(token_for_user(seeded_users["admin"].id)))
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["pagination"]["offset"] == 0
    assert payload["pagination"]["limit"] == 20


def test_get_schools_applies_limit_and_offset(client, seeded_users, db_session):
    """
    Validate schools list pagination slicing.

    1. Seed additional schools and memberships for current user.
    2. Call schools list endpoint with offset and limit once.
    3. Receive successful paginated response.
    4. Validate item count and pagination metadata.
    """
    school_one = create_school(db_session, "Offset One", "offset-one")
    school_two = create_school(db_session, "Offset Two", "offset-two")
    add_membership(db_session, seeded_users["admin"].id, school_one.id, UserRole.admin)
    add_membership(db_session, seeded_users["admin"].id, school_two.id, UserRole.admin)
    response = client.get(
        "/api/v1/schools?offset=1&limit=1", headers=auth_header(token_for_user(seeded_users["admin"].id))
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["pagination"]["offset"] == 1
    assert payload["pagination"]["limit"] == 1
    assert payload["pagination"]["filtered_total"] >= 3


def test_get_schools_applies_search_on_name_and_slug(client, seeded_users, db_session):
    """
    Validate schools list search filtering behavior.

    1. Seed one matching and one non-matching school for user.
    2. Call schools list endpoint with search param once.
    3. Receive successful paginated response.
    4. Validate only matching school is returned.
    """
    matching = create_school(db_session, "Needle Academy", "needle-academy")
    non_matching = create_school(db_session, "Other Campus", "other-campus")
    add_membership(db_session, seeded_users["admin"].id, matching.id, UserRole.admin)
    add_membership(db_session, seeded_users["admin"].id, non_matching.id, UserRole.admin)
    response = client.get(
        "/api/v1/schools?search=needle", headers=auth_header(token_for_user(seeded_users["admin"].id))
    )
    assert response.status_code == 200
    payload = response.json()
    slugs = {item["slug"] for item in payload["items"]}
    assert "needle-academy" in slugs
    assert "other-campus" not in slugs
    assert payload["pagination"]["filtered_total"] <= payload["pagination"]["total"]


def test_get_school_returns_400_when_header_is_missing(client, seeded_users):
    """
    Validate school get-by-id missing header branch.

    1. Build auth header without school selector.
    2. Call school get endpoint once.
    3. Receive bad request response.
    4. Validate X-School-Id is required.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=auth_header(token_for_user(seeded_users["admin"].id)),
    )
    assert response.status_code == 400


def test_get_school_returns_400_for_mismatched_path_and_header(client, seeded_users):
    """
    Validate school get-by-id header/path mismatch branch.

    1. Build admin header with different school id.
    2. Call school get endpoint once.
    3. Receive bad request response.
    4. Validate path school id must match header.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_get_school_returns_200_for_valid_header_and_membership(client, seeded_users):
    """
    Validate school get-by-id success branch.

    1. Build admin header for matching school id.
    2. Call school get endpoint once.
    3. Receive successful response.
    4. Validate returned school id.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == seeded_users["north_school"].id


def test_get_school_financial_summary_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate school financial summary success for admin users.

    1. Seed positive charges, one unpaid credit, and one payment in active school.
    2. Call school financial summary endpoint once as admin.
    3. Receive successful summary response.
    4. Validate charged, paid, pending, and student count values.
    """
    invoice = create_invoice(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        period="2026-07",
        issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        due_date=date(2026, 7, 10),
        total_amount="100.00",
        status=InvoiceStatus.open,
    )
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Debt A",
        amount="100.00",
        due_date=date(2026, 7, 10),
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
        invoice_id=invoice.id,
    )
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_two"].id,
        description="Debt B",
        amount="50.00",
        due_date=date(2026, 7, 10),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.paid,
        invoice_id=invoice.id,
    )
    create_charge(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        description="Credit",
        amount="-20.00",
        due_date=date(2026, 7, 10),
        charge_type=ChargeType.penalty,
        status=ChargeStatus.unpaid,
        invoice_id=invoice.id,
    )
    create_payment(
        db_session,
        school_id=seeded_users["north_school"].id,
        student_id=seeded_users["child_one"].id,
        invoice_id=invoice.id,
        amount="40.00",
        paid_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/financial-summary",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_billed_amount"] == "100.00"
    assert payload["total_charged_amount"] == "150.00"
    assert payload["total_paid_amount"] == "40.00"
    assert payload["total_pending_amount"] == "80.00"
    assert payload["student_count"] == 2
    assert set(payload["relevant_invoices"].keys()) == {"overdue_90_plus", "top_pending_open", "due_soon_7_days"}
    top_pending_ids = {item["invoice_id"] for item in payload["relevant_invoices"]["top_pending_open"]}
    assert invoice.id in top_pending_ids


def test_get_school_financial_summary_returns_empty_relevant_invoice_buckets(client, seeded_users, db_session):
    """
    Validate school financial summary returns empty relevant invoice buckets when no candidates exist.

    1. Seed a new school with admin membership but no invoices/payments.
    2. Call school financial summary endpoint once as admin.
    3. Receive successful summary response.
    4. Validate relevant invoice buckets are all empty arrays.
    """
    school = create_school(db_session, "Metrics Empty", "metrics-empty")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.get(
        f"/api/v1/schools/{school.id}/financial-summary",
        headers=school_header(token_for_user(seeded_users["admin"].id), school.id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["relevant_invoices"]["overdue_90_plus"] == []
    assert payload["relevant_invoices"]["top_pending_open"] == []
    assert payload["relevant_invoices"]["due_soon_7_days"] == []


def test_get_school_financial_summary_returns_403_for_non_admin(client, seeded_users):
    """
    Validate school financial summary forbidden for non-admin users.

    1. Build non-admin school-scoped header.
    2. Call school financial summary endpoint once.
    3. Receive forbidden response.
    4. Validate endpoint is admin-only.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/financial-summary",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 403


def test_get_school_financial_summary_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate school financial summary header/path mismatch branch.

    1. Build admin header with different school id.
    2. Call financial summary endpoint once.
    3. Receive bad request response.
    4. Validate path/header mismatch is rejected.
    """
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/financial-summary",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_enqueue_school_invoice_generation_returns_202_for_admin(client, seeded_users, monkeypatch):
    """
    Validate school-wide invoice generation enqueue succeeds for admin users.

    1. Mock enqueue helper to return a deterministic task id.
    2. Call enqueue endpoint once as admin in active school.
    3. Receive accepted response payload.
    4. Validate response status and task identifier.
    """

    monkeypatch.setattr(
        "app.interfaces.api.v1.routes.schools.enqueue_school_invoice_generation_task",
        lambda *, school_id: "task-123",
    )
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/invoices/generate-all",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 202
    assert response.json()["task_id"] == "task-123"
    assert response.json()["status"] == "queued"


def test_enqueue_school_invoice_generation_returns_403_for_non_admin(client, seeded_users):
    """
    Validate school-wide invoice generation enqueue is forbidden for non-admin users.

    1. Build non-admin school-scoped header.
    2. Call enqueue endpoint once.
    3. Receive forbidden response.
    4. Validate endpoint remains admin-only.
    """

    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/invoices/generate-all",
        headers=school_header(token_for_user(seeded_users["teacher"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 403


def test_enqueue_school_invoice_generation_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate school-wide enqueue rejects school path/header mismatch.

    1. Build admin header with different selected school id.
    2. Call enqueue endpoint once.
    3. Receive bad-request response.
    4. Validate school path must match X-School-Id.
    """

    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/invoices/generate-all",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_enqueue_school_invoice_generation_returns_503_when_enqueue_fails(client, seeded_users, monkeypatch):
    """
    Validate school-wide enqueue returns service unavailable when broker dispatch fails.

    1. Mock enqueue helper to raise runtime error.
    2. Call enqueue endpoint once as admin.
    3. Receive service unavailable response.
    4. Validate endpoint maps enqueue failures to 503.
    """

    def _raise_enqueue_error(*, school_id):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(
        "app.interfaces.api.v1.routes.schools.enqueue_school_invoice_generation_task",
        _raise_enqueue_error,
    )
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/invoices/generate-all",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 503


def test_enqueue_school_reconciliation_returns_202_for_admin(client, seeded_users, monkeypatch):
    """
    Validate reconciliation run enqueue succeeds for school admins.

    1. Mock reconciliation task enqueue helper to return deterministic task id.
    2. Call reconciliation enqueue endpoint once as admin.
    3. Receive accepted response payload.
    4. Validate task id and queued status fields.
    """

    monkeypatch.setattr(
        "app.interfaces.api.v1.routes.schools.enqueue_reconciliation_task",
        lambda *, run_id: "recon-task-123",
    )
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/run",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["task_id"] == "recon-task-123"
    assert payload["status"] == "queued"
    assert isinstance(payload["run_id"], int)


def test_enqueue_school_reconciliation_returns_503_when_enqueue_fails(client, seeded_users, monkeypatch):
    """
    Validate reconciliation enqueue maps dispatch failures to 503.

    1. Mock reconciliation enqueue helper to raise runtime error.
    2. Call reconciliation enqueue endpoint once as admin.
    3. Receive service unavailable response.
    4. Validate status code is 503.
    """

    def _raise(*, run_id):
        raise RuntimeError("broker down")

    monkeypatch.setattr("app.interfaces.api.v1.routes.schools.enqueue_reconciliation_task", _raise)
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/run",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 503


def test_enqueue_school_reconciliation_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate reconciliation enqueue rejects school path/header mismatch.

    1. Build admin header for different selected school.
    2. Call reconciliation enqueue endpoint once.
    3. Receive bad-request response.
    4. Validate path school id must match X-School-Id.
    """

    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/run",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_get_school_reconciliation_runs_returns_paginated_list_for_admin(client, seeded_users, db_session):
    """
    Validate reconciliation runs endpoint returns paginated list for admins.

    1. Seed one reconciliation run for active school.
    2. Call list runs endpoint once as admin.
    3. Receive successful paginated response.
    4. Validate run id appears in response items.
    """

    run = ReconciliationRun(
        school_id=seeded_users["north_school"].id,
        triggered_by_user_id=seeded_users["admin"].id,
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        summary_json={"findings_total": 0},
    )
    persist_entity(db_session, run)
    refresh_entity(db_session, run)
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/runs",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    assert any(item["id"] == run.id for item in response.json()["items"])


def test_get_school_reconciliation_run_detail_returns_findings_for_admin(client, seeded_users, db_session):
    """
    Validate reconciliation run detail endpoint returns persisted findings.

    1. Seed one reconciliation run and one finding in active school.
    2. Call run detail endpoint once as admin.
    3. Receive successful response payload.
    4. Validate run and finding identifiers match seeded records.
    """

    run = ReconciliationRun(
        school_id=seeded_users["north_school"].id,
        triggered_by_user_id=seeded_users["admin"].id,
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        summary_json={"findings_total": 1},
    )
    persist_entity(db_session, run)
    finding = ReconciliationFinding(
        run_id=run.id,
        school_id=seeded_users["north_school"].id,
        check_code="invoice_total_mismatch",
        severity="high",
        entity_type="invoice",
        entity_id=10,
        message="mismatch",
        details_json={"invoice_total": "10.00", "items_total": "9.00"},
    )
    persist_entity(db_session, finding)
    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/runs/{run.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == run.id
    assert payload["findings"][0]["id"] == finding.id


def test_get_school_reconciliation_runs_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate reconciliation runs list rejects school path/header mismatch.

    1. Build admin header for different selected school id.
    2. Call reconciliation runs list endpoint once.
    3. Receive bad-request response.
    4. Validate path school id must match X-School-Id.
    """

    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/runs",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_get_school_reconciliation_run_detail_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate reconciliation run detail rejects school path/header mismatch.

    1. Build admin header for different selected school id.
    2. Call reconciliation run detail endpoint once.
    3. Receive bad-request response.
    4. Validate path school id must match X-School-Id.
    """

    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/runs/1",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400


def test_get_school_reconciliation_run_detail_returns_404_for_missing_run(client, seeded_users):
    """
    Validate reconciliation run detail returns not found for unknown run id.

    1. Build admin header for active school.
    2. Call run detail endpoint with unknown id.
    3. Receive not-found response.
    4. Validate missing run path is covered.
    """

    response = client.get(
        f"/api/v1/schools/{seeded_users['north_school'].id}/reconciliation/runs/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 404


def test_create_school_returns_201_for_school_admin(client, seeded_users):
    """
    Validate school creation success for school admin.

    1. Build admin school-scoped header.
    2. Call create school endpoint once.
    3. Receive created response.
    4. Validate creator appears with admin role.
    """
    response = client.post(
        "/api/v1/schools",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Endpoint School", "slug": "endpoint-school"},
    )
    assert response.status_code == 201
    roles_map = {member["user_id"]: member["roles"] for member in response.json()["members"]}
    assert "admin" in roles_map[seeded_users["admin"].id]


def test_create_school_returns_409_for_duplicate_slug(client, seeded_users, db_session):
    """
    Validate school creation duplicate slug conflict.

    1. Seed school with target slug.
    2. Call create school endpoint with duplicate slug.
    3. Receive conflict response.
    4. Validate duplicate slug is rejected.
    """
    create_school(db_session, "Existing", "dup-school")
    response = client.post(
        "/api/v1/schools",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Duplicate", "slug": "dup-school"},
    )
    assert response.status_code == 409


def test_create_school_returns_403_for_non_admin(client, seeded_users):
    """
    Validate school creation forbidden for non-admin.

    1. Build student school-scoped header.
    2. Call create school endpoint once.
    3. Receive forbidden response.
    4. Validate non-admin cannot create schools.
    """
    response = client.post(
        "/api/v1/schools",
        headers=school_header(token_for_user(seeded_users["student"].id), seeded_users["north_school"].id),
        json={"name": "Forbidden", "slug": "forbidden-school"},
    )
    assert response.status_code == 403


def test_update_school_returns_200_for_admin(client, seeded_users, db_session):
    """
    Validate school update success for admin.

    1. Seed a school and add admin membership for same school.
    2. Call update school endpoint once.
    3. Receive successful response.
    4. Validate updated name field.
    """
    school = create_school(db_session, "To Update", "to-update")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.put(
        f"/api/v1/schools/{school.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), school.id),
        json={"name": "Updated School"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated School"


def test_update_school_returns_400_for_mismatched_header(client, seeded_users, db_session):
    """
    Validate school update header/path mismatch branch.

    1. Seed school and admin membership.
    2. Call update endpoint with different school id header.
    3. Receive bad request response.
    4. Validate path/header mismatch is rejected.
    """
    school = create_school(db_session, "Mismatch", "mismatch")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.put(
        f"/api/v1/schools/{school.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"name": "Mismatch"},
    )
    assert response.status_code == 400


def test_update_school_returns_404_for_missing_school(client, seeded_users):
    """
    Validate school update missing-school branch.

    1. Build admin header matching missing school id.
    2. Call update endpoint with non-existing id.
    3. Receive not found response.
    4. Validate missing schools return 404.
    """
    response = client.put(
        "/api/v1/schools/999999",
        headers=school_header(token_for_user(seeded_users["admin"].id), 999999),
        json={"name": "Missing"},
    )
    assert response.status_code == 404


def test_associate_user_to_school_returns_201_for_admin(client, seeded_users):
    """
    Validate user-school association success.

    1. Build admin school-scoped header.
    2. Call school-user association endpoint once.
    3. Receive created response.
    4. Validate status code is 201.
    """
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"user_id": seeded_users["teacher"].id, "role": "admin"},
    )
    assert response.status_code == 201


def test_associate_user_to_school_returns_404_for_missing_user(client, seeded_users):
    """
    Validate user-school association missing-user branch.

    1. Build admin school-scoped header.
    2. Call association endpoint with unknown user id.
    3. Receive not found response.
    4. Validate missing user returns 404.
    """
    response = client.post(
        f"/api/v1/schools/{seeded_users['north_school'].id}/users",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
        json={"user_id": 999999, "role": "teacher"},
    )
    assert response.status_code == 404


def test_deassociate_user_from_school_returns_204_for_admin(client, seeded_users):
    """
    Validate user-school deassociation success.

    1. Build admin school-scoped header.
    2. Call deassociation endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    response = client.delete(
        f"/api/v1/schools/{seeded_users['north_school'].id}/users/{seeded_users['teacher'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["north_school"].id),
    )
    assert response.status_code == 204


def test_delete_school_returns_204_for_admin(client, seeded_users, db_session):
    """
    Validate school deletion success for admin.

    1. Seed school and add admin membership.
    2. Call delete school endpoint once.
    3. Receive no-content response.
    4. Validate status code is 204.
    """
    school = create_school(db_session, "Delete School", "delete-school")
    add_membership(db_session, seeded_users["admin"].id, school.id, UserRole.admin)
    response = client.delete(
        f"/api/v1/schools/{school.id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), school.id),
    )
    assert response.status_code == 204


def test_delete_school_returns_400_for_mismatched_header(client, seeded_users):
    """
    Validate school deletion header/path mismatch branch.

    1. Build admin header for different school id.
    2. Call delete school endpoint once.
    3. Receive bad request response.
    4. Validate path/header mismatch is rejected.
    """
    response = client.delete(
        f"/api/v1/schools/{seeded_users['north_school'].id}",
        headers=school_header(token_for_user(seeded_users["admin"].id), seeded_users["south_school"].id),
    )
    assert response.status_code == 400
