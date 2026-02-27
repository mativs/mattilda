from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import cast

from app.application.services.pagination_service import paginate_scalars
from app.application.services.reconciliation_service import (
    create_queued_reconciliation_run,
    get_reconciliation_run_with_findings,
    list_reconciliation_runs_query,
    serialize_reconciliation_finding,
    serialize_reconciliation_run,
)
from app.application.services.school_service import (
    add_user_school_role,
    create_school,
    delete_school,
    get_school_financial_summary,
    get_school_by_id,
    remove_user_school_roles,
    serialize_school_response,
    update_school,
)
from app.domain.roles import UserRole
from app.infrastructure.db.models import ReconciliationRun, School, User, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.infrastructure.logging import get_logger
from app.infrastructure.tasks.invoice_tasks import enqueue_school_invoice_generation_task
from app.infrastructure.tasks.reconciliation_tasks import enqueue_reconciliation_task
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school,
    get_current_school_id,
    get_current_school_memberships,
    require_authenticated,
    require_school_admin,
    require_school_roles,
)
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.pagination import PaginationParams
from app.interfaces.api.v1.schemas.school import (
    ReconciliationRunDetailResponse,
    ReconciliationRunListResponse,
    ReconciliationRunTaskResponse,
    SchoolCreate,
    SchoolFinancialSummaryResponse,
    SchoolInvoiceGenerationTaskResponse,
    SchoolListResponse,
    SchoolResponse,
    SchoolUpdate,
)
from app.interfaces.api.v1.schemas.student import UserSchoolMembershipPayload

router = APIRouter(prefix="/schools", tags=["schools"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=SchoolListResponse,
    summary="List user schools",
    description="List schools where current user has membership.",
    responses={401: {"description": "Unauthorized"}},
)
def get_schools(
    current_user: User = Depends(require_authenticated),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    base_query = (
        select(School)
        .distinct(School.id)
        .join(UserSchoolRole, UserSchoolRole.school_id == School.id)
        .where(UserSchoolRole.user_id == current_user.id, School.deleted_at.is_(None))
        .order_by(School.id)
    )
    schools, meta = paginate_scalars(
        db=db,
        base_query=base_query,
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[School.name, School.slug],
    )
    return {"items": [serialize_school_response(school) for school in schools], "pagination": meta}


@router.post(
    "",
    response_model=SchoolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create school",
    description="Create a school and auto-assign creator as school admin.",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def create_school_endpoint(
    payload: SchoolCreate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school = create_school(db=db, payload=payload, creator_user_id=current_user.id)
    return serialize_school_response(school)


@router.get(
    "/{school_id}",
    response_model=SchoolResponse,
    summary="Get school by id",
    description="Return school details. Path `school_id` must match `X-School-Id`.",
    responses={401: {"description": "Unauthorized"}, 400: {"description": "Path/header school mismatch"}},
)
def get_school(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    school: School = Depends(get_current_school),
    _: list[UserSchoolRole] = Depends(get_current_school_memberships),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    return serialize_school_response(school)


@router.put(
    "/{school_id}",
    response_model=SchoolResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Update school",
    description="Admin-only school update for active school; path id must match `X-School-Id`.",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
    },
)
def update_school_endpoint(
    school_id: int,
    payload: SchoolUpdate,
    selected_school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    school = cast(School, get_school_by_id(db=db, school_id=school_id))
    updated_school = update_school(db=db, school=school, payload=payload)
    return serialize_school_response(updated_school)


@router.delete(
    "/{school_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Delete school (soft delete)",
    description="Admin-only school soft delete; path id must match `X-School-Id`.",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
    },
)
def delete_school_endpoint(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    school = cast(School, get_school_by_id(db=db, school_id=school_id))
    delete_school(db=db, school=school)


@router.get(
    "/{school_id}/financial-summary",
    response_model=SchoolFinancialSummaryResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Get school financial summary",
    description="Admin-only financial KPIs and relevant invoices for active school.",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
    },
)
def get_school_financial_summary_endpoint(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    return get_school_financial_summary(db=db, school_id=school_id)


@router.post(
    "/{school_id}/invoices/generate-all",
    response_model=SchoolInvoiceGenerationTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Enqueue school-wide invoice generation",
    description=(
        "Admin-only async task enqueue for generating invoices for all school students. "
        "Returns queue metadata immediately."
    ),
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
        503: {"description": "Task enqueue failed"},
    },
)
def enqueue_school_invoice_generation(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    logger.info("school_invoice_generation_enqueue_requested", school_id=school_id)
    try:
        task_id = enqueue_school_invoice_generation_task(school_id=school_id)
    except Exception as exc:
        logger.error("school_invoice_generation_enqueue_failed", school_id=school_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to enqueue invoice generation task") from exc
    logger.info("school_invoice_generation_enqueued", school_id=school_id, task_id=task_id)
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "School invoice generation started",
    }


@router.post(
    "/{school_id}/reconciliation/run",
    response_model=ReconciliationRunTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Enqueue school reconciliation run",
    description="Admin-only async enqueue for reconciliation checks in active school.",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
        503: {"description": "Task enqueue failed"},
    },
)
def enqueue_school_reconciliation(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    logger.info("school_reconciliation_enqueue_requested", school_id=school_id, user_id=current_user.id)
    run = create_queued_reconciliation_run(
        db=db,
        school_id=school_id,
        triggered_by_user_id=current_user.id,
    )
    try:
        task_id = enqueue_reconciliation_task(run_id=run.id)
    except Exception as exc:
        logger.error("school_reconciliation_enqueue_failed", school_id=school_id, run_id=run.id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to enqueue reconciliation task") from exc
    logger.info("school_reconciliation_enqueued", school_id=school_id, run_id=run.id, task_id=task_id)
    return {
        "task_id": task_id,
        "run_id": run.id,
        "status": "queued",
        "message": "School reconciliation queued",
    }


@router.get(
    "/{school_id}/reconciliation/runs",
    response_model=ReconciliationRunListResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="List reconciliation runs",
    description="Admin-only paginated reconciliation run history for active school.",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
    },
)
def get_school_reconciliation_runs(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    runs, meta = paginate_scalars(
        db=db,
        base_query=list_reconciliation_runs_query(school_id=school_id),
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[ReconciliationRun.status],
    )
    return {"items": [serialize_reconciliation_run(run) for run in runs], "pagination": meta}


@router.get(
    "/{school_id}/reconciliation/runs/{run_id}",
    response_model=ReconciliationRunDetailResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Get reconciliation run detail",
    description="Admin-only run detail with ordered findings for active school.",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Path/header school mismatch"},
        404: {"description": "Run not found"},
    },
)
def get_school_reconciliation_run_detail(
    school_id: int,
    run_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    run = get_reconciliation_run_with_findings(db=db, school_id=school_id, run_id=run_id)
    findings = sorted(run.findings, key=lambda item: (item.check_code, item.severity, item.id))
    return {
        "run": serialize_reconciliation_run(run),
        "findings": [serialize_reconciliation_finding(finding) for finding in findings],
    }


@router.post(
    "/{school_id}/users",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_admin)],
    summary="Associate user with school",
    description="Admin-only association of a user and role into a school.",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def associate_user_with_school(school_id: int, payload: UserSchoolMembershipPayload, db: Session = Depends(get_db)):
    add_user_school_role(db=db, school_id=school_id, user_id=payload.user_id, role=payload.role.value)
    return {"message": "User associated to school"}


@router.delete(
    "/{school_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_school_admin)],
    summary="Deassociate user from school",
    description="Admin-only removal of all user roles from a school.",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def deassociate_user_from_school(school_id: int, user_id: int, db: Session = Depends(get_db)):
    remove_user_school_roles(db=db, school_id=school_id, user_id=user_id)
