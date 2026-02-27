from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.charge_service import (
    create_charge,
    delete_charge,
    get_charge_by_id,
    serialize_charge_response,
    update_charge,
)
from app.application.services.pagination_service import paginate_scalars
from app.domain.roles import UserRole
from app.infrastructure.db.models import Charge, Student
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import get_current_school_id, require_school_roles
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.charge import ChargeCreate, ChargeListResponse, ChargeResponse, ChargeUpdate
from app.interfaces.api.v1.schemas.pagination import PaginationParams

router = APIRouter(prefix="/charges", tags=["charges"])


@router.get(
    "",
    response_model=ChargeListResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="List charges",
    description="List charges for the active school (`X-School-Id`) with pagination and search (admin only).",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def get_charges(
    school_id: int = Depends(get_current_school_id),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    base_query = (
        select(Charge)
        .join(Student, Student.id == Charge.student_id)
        .where(Charge.school_id == school_id, Charge.deleted_at.is_(None))
        .order_by(Charge.id)
    )
    items, meta = paginate_scalars(
        db=db,
        base_query=base_query,
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[Charge.description, Charge.period, Student.first_name, Student.last_name],
    )
    return {"items": [serialize_charge_response(item) for item in items], "pagination": meta}


@router.post(
    "",
    response_model=ChargeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Create charge",
    description="Create a charge for a student in the active school (admin only).",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def create_charge_endpoint(
    payload: ChargeCreate,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    charge = create_charge(db=db, school_id=school_id, payload=payload)
    return serialize_charge_response(charge)


@router.get(
    "/{charge_id}",
    response_model=ChargeResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Get charge by id",
    description="Fetch one charge from the active school (admin only).",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        404: {"description": "Charge not found"},
    },
)
def get_charge_endpoint(charge_id: int, school_id: int = Depends(get_current_school_id), db: Session = Depends(get_db)):
    charge = get_charge_by_id(db=db, charge_id=charge_id, school_id=school_id)
    if charge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge not found")
    return serialize_charge_response(charge)


@router.put(
    "/{charge_id}",
    response_model=ChargeResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Update charge",
    description="Update mutable fields of a charge in the active school (admin only).",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        404: {"description": "Charge not found"},
    },
)
def update_charge_endpoint(
    charge_id: int,
    payload: ChargeUpdate,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    charge = get_charge_by_id(db=db, charge_id=charge_id, school_id=school_id)
    if charge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge not found")
    updated = update_charge(db=db, charge=charge, payload=payload)
    return serialize_charge_response(updated)


@router.delete(
    "/{charge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Delete charge (soft delete)",
    description="Soft-delete a charge and mark it cancelled in the active school (admin only).",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        404: {"description": "Charge not found"},
    },
)
def delete_charge_endpoint(
    charge_id: int, school_id: int = Depends(get_current_school_id), db: Session = Depends(get_db)
):
    charge = get_charge_by_id(db=db, charge_id=charge_id, school_id=school_id)
    if charge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charge not found")
    delete_charge(db=db, charge=charge)
