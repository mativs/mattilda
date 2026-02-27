from app.application.services.school_invoice_generation_service import generate_invoices_for_school
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.tasks.celery_app import celery_app


@celery_app.task(name="schools.generate_invoices_for_school")
def generate_invoices_for_school_task(school_id: int) -> dict:
    db = SessionLocal()
    try:
        return generate_invoices_for_school(db=db, school_id=school_id)
    finally:
        db.close()


def enqueue_school_invoice_generation_task(*, school_id: int) -> str:
    task = generate_invoices_for_school_task.delay(school_id=school_id)
    return str(task.id)
