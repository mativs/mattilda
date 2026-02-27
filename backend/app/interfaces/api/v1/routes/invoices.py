from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.application.services.invoice_service import (
    build_visible_invoices_query_for_student,
    get_visible_invoice_by_id,
    get_visible_invoice_items,
    get_visible_student_for_invoice_access,
    serialize_invoice_detail,
    serialize_invoice_summary,
)
from app.application.services.invoice_generation_service import generate_invoice_for_student
from app.application.services.pagination_service import paginate_scalars
from app.domain.roles import UserRole
from app.infrastructure.db.models import Invoice, Student, User, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school_id,
    get_current_school_memberships,
    require_authenticated,
    require_school_roles,
)
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.invoice import (
    InvoiceDetailResponse,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceSummaryResponse,
)
from app.interfaces.api.v1.schemas.pagination import PaginationParams

router = APIRouter(tags=["invoices"])


@router.get(
    "/students/{student_id}/invoices",
    response_model=InvoiceListResponse,
    summary="List student invoices",
    description=(
        "Return invoice summaries visible to the current user for a student in the active school. "
        "Requires `Authorization: Bearer <token>` and `X-School-Id`."
    ),
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Student not found"}},
)
def get_student_invoices(
    student_id: int,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    is_admin = any(link.role == UserRole.admin.value for link in memberships)
    visible_student = get_visible_student_for_invoice_access(
        db=db,
        student_id=student_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    if visible_student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    base_query = build_visible_invoices_query_for_student(
        student_id=student_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    items, meta = paginate_scalars(
        db=db,
        base_query=base_query,
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[
            Invoice.period,
            Student.first_name,
            Student.last_name,
            cast(Invoice.status, String),
        ],
    )
    return {"items": [serialize_invoice_summary(item) for item in items], "pagination": meta}


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceDetailResponse,
    summary="Get invoice detail",
    description="Return one invoice with item snapshot details when visible to caller in active school.",
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Invoice not found"}},
)
def get_invoice_detail(
    invoice_id: int,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    db: Session = Depends(get_db),
):
    invoice = get_visible_invoice_by_id(
        db=db,
        invoice_id=invoice_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=any(link.role == UserRole.admin.value for link in memberships),
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return serialize_invoice_detail(invoice)


@router.get(
    "/invoices/{invoice_id}/items",
    response_model=list[InvoiceItemResponse],
    summary="List invoice items",
    description="Return immutable invoice line items for a visible invoice in active school.",
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Invoice not found"}},
)
def get_invoice_items(
    invoice_id: int,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    db: Session = Depends(get_db),
):
    items = get_visible_invoice_items(
        db=db,
        invoice_id=invoice_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=any(link.role == UserRole.admin.value for link in memberships),
    )
    if items is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return items


@router.post(
    "/students/{student_id}/invoices/generate",
    response_model=InvoiceSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Generate invoice for student",
    description=(
        "Admin-only operation for active school (`X-School-Id`): closes existing open invoice, "
        "applies overdue interest delta rules, and creates a new invoice snapshot from unpaid charges."
    ),
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        400: {"description": "Validation error while generating invoice"},
    },
)
def generate_student_invoice(
    student_id: int,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    invoice = generate_invoice_for_student(db=db, school_id=school_id, student_id=student_id)
    db.refresh(invoice)
    return serialize_invoice_summary(invoice)
