from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.application.services.pagination_service import paginate_scalars
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
    require_school_roles,
)
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.pagination import PaginationParams
from app.interfaces.api.v1.schemas.payment import PaymentCreate, PaymentListResponse, PaymentResponse

router = APIRouter(tags=["payments"])


@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
)
def create_payment_endpoint(
    payload: PaymentCreate,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    payment = create_payment(db=db, school_id=school_id, payload=payload)
    return serialize_payment_response(payment)


@router.get("/students/{student_id}/payments", response_model=PaymentListResponse)
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


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
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
