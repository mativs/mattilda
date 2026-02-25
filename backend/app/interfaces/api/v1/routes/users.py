from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.services.user_service import create_user, delete_user, get_user_by_id, list_users, update_user
from app.domain.roles import UserRole
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import require_authenticated, require_roles, require_self_or_roles
from app.interfaces.api.v1.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse], dependencies=[Depends(require_roles([UserRole.admin]))])
def get_users(db: Session = Depends(get_db)):
    return list_users(db=db)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles([UserRole.admin]))])
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)):
    return create_user(db=db, payload=payload)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(require_authenticated)):
    return current_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_self_or_roles("user_id", [UserRole.admin]))],
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_roles([UserRole.admin]))])
def update_user_endpoint(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return update_user(db=db, user=user, payload=payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles([UserRole.admin]))])
def delete_user_endpoint(user_id: int, db: Session = Depends(get_db)):
    user = get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    delete_user(db=db, user=user)
