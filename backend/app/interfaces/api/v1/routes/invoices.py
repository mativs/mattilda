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
from app.application.services.pagination_service import paginate_scalars
from app.domain.roles import UserRole
from app.infrastructure.db.models import Invoice, Student, User, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school_id,
    get_current_school_memberships,
    require_authenticated,
)
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.invoice import (
    InvoiceDetailResponse,
    InvoiceItemResponse,
    InvoiceListResponse,
)
from app.interfaces.api.v1.schemas.pagination import PaginationParams

router = APIRouter(tags=["invoices"])


@router.get("/students/{student_id}/invoices", response_model=InvoiceListResponse)
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


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
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


@router.get("/invoices/{invoice_id}/items", response_model=list[InvoiceItemResponse])
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
