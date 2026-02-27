from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.application.services.pagination_service import paginate_scalars
from app.application.services.payment_lock_service import payment_creation_lock
from app.application.services.payment_service import (
    build_visible_payments_query_for_student,
    create_payment,
    get_visible_payment_by_id,
    get_visible_student_for_payment_access,
    serialize_payment_response,
)
from app.domain.roles import UserRole
from app.infrastructure.db.models import Payment, Student, User, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school_id,
    get_current_school_memberships,
    require_authenticated,
)
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.pagination import PaginationParams
from app.interfaces.api.v1.schemas.payment import PaymentCreate, PaymentListResponse, PaymentResponse

router = APIRouter(tags=["payments"])


@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment",
    description=(
        "Create a payment for an invoice in the active school (`X-School-Id`). "
        "Allowed for school admins and student users paying their own visible student. "
        "Payment processing uses a short Redis lock to prevent duplicate submits."
    ),
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school permissions"},
        404: {"description": "Student not found"},
        400: {"description": "Payment validation error"},
    },
)
def create_payment_endpoint(
    payload: PaymentCreate,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    db: Session = Depends(get_db),
):
    is_admin = any(link.role == UserRole.admin.value for link in memberships)
    is_student = any(link.role == UserRole.student.value for link in memberships)
    if not is_admin and not is_student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient school permissions")
    if not is_admin:
        visible_student = get_visible_student_for_payment_access(
            db=db,
            student_id=payload.student_id,
            school_id=school_id,
            user_id=current_user.id,
            is_admin=False,
        )
        if visible_student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    with payment_creation_lock(school_id=school_id, invoice_id=payload.invoice_id):
        payment = create_payment(db=db, school_id=school_id, payload=payload)
    return serialize_payment_response(payment)


@router.get(
    "/students/{student_id}/payments",
    response_model=PaymentListResponse,
    summary="List student payments",
    description=(
        "List payments for a student visible to caller in active school (`X-School-Id`) with pagination/search."
    ),
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Student not found"}},
)
def get_student_payments(
    student_id: int,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    is_admin = any(link.role == UserRole.admin.value for link in memberships)
    visible_student = get_visible_student_for_payment_access(
        db=db,
        student_id=student_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    if visible_student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    base_query = build_visible_payments_query_for_student(
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
            Payment.method,
            cast(Payment.amount, String),
            Student.first_name,
            Student.last_name,
        ],
    )
    return {"items": [serialize_payment_response(item) for item in items], "pagination": meta}


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment detail",
    description="Return one payment when visible to caller in active school.",
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Payment not found"}},
)
def get_payment_detail(
    payment_id: int,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    db: Session = Depends(get_db),
):
    payment = get_visible_payment_by_id(
        db=db,
        payment_id=payment_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=any(link.role == UserRole.admin.value for link in memberships),
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return serialize_payment_response(payment)
