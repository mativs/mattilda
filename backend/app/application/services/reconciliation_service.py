from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.application.errors import NotFoundError
from app.application.services.reconciliation_checks_service import run_all_reconciliation_checks
from app.infrastructure.db.models import ReconciliationFinding, ReconciliationRun
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)


def _build_summary(*, findings: list[dict]) -> dict:
    by_check: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for finding in findings:
        check_code = str(finding["check_code"])
        severity = str(finding["severity"])
        by_check[check_code] = by_check.get(check_code, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {"findings_total": len(findings), "by_check": by_check, "by_severity": by_severity}


def run_school_reconciliation(db: Session, *, school_id: int, triggered_by_user_id: int | None = None) -> ReconciliationRun:
    run = create_queued_reconciliation_run(
        db=db,
        school_id=school_id,
        triggered_by_user_id=triggered_by_user_id,
    )
    return execute_reconciliation_run(db=db, run_id=run.id)


def create_queued_reconciliation_run(
    db: Session, *, school_id: int, triggered_by_user_id: int | None = None
) -> ReconciliationRun:
    run = ReconciliationRun(
        school_id=school_id,
        triggered_by_user_id=triggered_by_user_id,
        status="queued",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(
        "reconciliation_run_queued",
        run_id=run.id,
        school_id=school_id,
        triggered_by_user_id=triggered_by_user_id,
    )
    return run


def execute_reconciliation_run(db: Session, *, run_id: int) -> ReconciliationRun:
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise NotFoundError("Reconciliation run not found")
    started_at = datetime.now(timezone.utc)
    run.status = "running"
    run.started_at = started_at
    logger.info("reconciliation_run_started", run_id=run.id, school_id=run.school_id)
    db.flush()
    findings = run_all_reconciliation_checks(db=db, school_id=run.school_id, as_of=started_at)
    for finding in findings:
        db.add(
            ReconciliationFinding(
                run_id=run.id,
                school_id=run.school_id,
                check_code=str(finding["check_code"]),
                severity=str(finding["severity"]),
                entity_type=finding.get("entity_type"),
                entity_id=finding.get("entity_id"),
                message=str(finding["message"]),
                details_json=finding.get("details_json"),
            )
        )
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    run.summary_json = _build_summary(findings=findings)
    db.commit()
    db.refresh(run)
    logger.info(
        "reconciliation_run_completed",
        run_id=run.id,
        school_id=run.school_id,
        findings_total=run.summary_json.get("findings_total", 0) if run.summary_json else 0,
    )
    return run


def mark_reconciliation_run_failed(db: Session, *, run_id: int, error_message: str) -> None:
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        return
    run.status = "failed"
    run.finished_at = datetime.now(timezone.utc)
    run.summary_json = {"error": error_message}
    db.commit()
    logger.error("reconciliation_run_failed", run_id=run_id, school_id=run.school_id, error=error_message)


def serialize_reconciliation_finding(finding: ReconciliationFinding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "run_id": finding.run_id,
        "school_id": finding.school_id,
        "check_code": finding.check_code,
        "severity": finding.severity,
        "entity_type": finding.entity_type,
        "entity_id": finding.entity_id,
        "message": finding.message,
        "details_json": finding.details_json,
        "created_at": finding.created_at,
        "updated_at": finding.updated_at,
    }


def serialize_reconciliation_run(run: ReconciliationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "school_id": run.school_id,
        "triggered_by_user_id": run.triggered_by_user_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "summary_json": run.summary_json,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def list_reconciliation_runs_query(*, school_id: int):
    return (
        select(ReconciliationRun)
        .where(ReconciliationRun.school_id == school_id)
        .order_by(ReconciliationRun.started_at.desc(), ReconciliationRun.id.desc())
    )


def get_reconciliation_run_with_findings(
    db: Session, *, school_id: int, run_id: int
) -> ReconciliationRun:
    run = db.execute(
        select(ReconciliationRun)
        .where(ReconciliationRun.id == run_id, ReconciliationRun.school_id == school_id)
        .options(selectinload(ReconciliationRun.findings))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Reconciliation run not found")
    return run
