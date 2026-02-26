from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.pagination_service import paginate_scalars
from app.application.services.user_service import (
    create_user,
    delete_user,
    get_user_by_id,
    serialize_user_response,
    update_user,
)
from app.domain.roles import UserRole
from app.infrastructure.db.models import User, UserProfile, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school_id,
    require_authenticated,
    require_school_roles,
    require_self_or_school_roles,
)
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.pagination import PaginationParams
from app.interfaces.api.v1.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse, dependencies=[Depends(require_school_roles([UserRole.admin]))])
def get_users(
    school_id: int = Depends(get_current_school_id),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    base_query = (
        select(User)
        .distinct(User.id)
        .join(UserSchoolRole, UserSchoolRole.user_id == User.id)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(UserSchoolRole.school_id == school_id, User.deleted_at.is_(None))
        .order_by(User.id)
    )
    users, meta = paginate_scalars(
        db=db,
        base_query=base_query,
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[User.email, UserProfile.first_name, UserProfile.last_name],
    )
    return {"items": [serialize_user_response(user) for user in users], "pagination": meta}


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_roles([UserRole.admin]))],
)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)):
    user = create_user(db=db, payload=payload)
    return serialize_user_response(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(require_authenticated)):
    return serialize_user_response(current_user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_self_or_school_roles("user_id", [UserRole.admin]))],
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return serialize_user_response(user)


@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_school_roles([UserRole.admin]))])
def update_user_endpoint(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated = update_user(db=db, user=user, payload=payload)
    return serialize_user_response(updated)


@router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_school_roles([UserRole.admin]))]
)
def delete_user_endpoint(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    delete_user(db=db, user=user)
