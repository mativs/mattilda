from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.fee_service import (
    create_fee_definition,
    delete_fee_definition,
    get_fee_definition_by_id,
    serialize_fee_response,
    update_fee_definition,
)
from app.application.services.pagination_service import paginate_scalars
from app.domain.roles import UserRole
from app.infrastructure.db.models import FeeDefinition
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import get_current_school_id, require_school_roles
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.fee import FeeCreate, FeeListResponse, FeeResponse, FeeUpdate
from app.interfaces.api.v1.schemas.pagination import PaginationParams

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get(
    "",
    response_model=FeeListResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="List fee definitions",
    description="List fee definitions for the active school selected by `X-School-Id` (admin only).",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def get_fees(
    school_id: int = Depends(get_current_school_id),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    base_query = (
        select(FeeDefinition)
        .where(FeeDefinition.school_id == school_id, FeeDefinition.deleted_at.is_(None))
        .order_by(FeeDefinition.id)
    )
    items, meta = paginate_scalars(
        db=db,
        base_query=base_query,
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[FeeDefinition.name],
    )
    return {"items": [serialize_fee_response(item) for item in items], "pagination": meta}


@router.post(
    "",
    response_model=FeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Create fee definition",
    description="Create a fee definition for the active school (admin only).",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Insufficient school role"}},
)
def create_fee_endpoint(
    payload: FeeCreate,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    fee = create_fee_definition(db=db, school_id=school_id, payload=payload)
    return serialize_fee_response(fee)


@router.get(
    "/{fee_id}",
    response_model=FeeResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Get fee definition by id",
    description="Fetch one fee definition from the active school (admin only).",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        404: {"description": "Fee definition not found"},
    },
)
def get_fee_endpoint(fee_id: int, school_id: int = Depends(get_current_school_id), db: Session = Depends(get_db)):
    fee = get_fee_definition_by_id(db=db, fee_id=fee_id, school_id=school_id)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee definition not found")
    return serialize_fee_response(fee)


@router.put(
    "/{fee_id}",
    response_model=FeeResponse,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Update fee definition",
    description="Update mutable fields of a fee definition in the active school (admin only).",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        404: {"description": "Fee definition not found"},
    },
)
def update_fee_endpoint(
    fee_id: int,
    payload: FeeUpdate,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    fee = get_fee_definition_by_id(db=db, fee_id=fee_id, school_id=school_id)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee definition not found")
    updated = update_fee_definition(db=db, fee=fee, payload=payload)
    return serialize_fee_response(updated)


@router.delete(
    "/{fee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
    summary="Delete fee definition (soft delete)",
    description="Soft-delete a fee definition in the active school (admin only).",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient school role"},
        404: {"description": "Fee definition not found"},
    },
)
def delete_fee_endpoint(fee_id: int, school_id: int = Depends(get_current_school_id), db: Session = Depends(get_db)):
    fee = get_fee_definition_by_id(db=db, fee_id=fee_id, school_id=school_id)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee definition not found")
    delete_fee_definition(db=db, fee=fee)
