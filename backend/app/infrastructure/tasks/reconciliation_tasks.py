from app.application.services.reconciliation_service import execute_reconciliation_run, mark_reconciliation_run_failed
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.logging import get_logger
from app.infrastructure.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="schools.run_reconciliation")
def run_reconciliation_task(run_id: int) -> dict:
    db = SessionLocal()
    logger.info("reconciliation_task_started", run_id=run_id)
    try:
        run = execute_reconciliation_run(db=db, run_id=run_id)
        logger.info("reconciliation_task_completed", run_id=run_id, status=run.status)
        return {"run_id": run.id, "status": run.status, "summary_json": run.summary_json}
    except Exception as exc:
        mark_reconciliation_run_failed(db=db, run_id=run_id, error_message=str(exc))
        logger.error("reconciliation_task_failed", run_id=run_id, error=str(exc))
        raise
    finally:
        db.close()


def enqueue_reconciliation_task(*, run_id: int) -> str:
    task = run_reconciliation_task.delay(run_id=run_id)
    return str(task.id)
