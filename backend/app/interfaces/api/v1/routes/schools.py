from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.services.school_service import (
    add_user_school_role,
    create_school,
    delete_school,
    get_school_by_id,
    list_schools_for_user,
    remove_user_school_roles,
    serialize_school_response,
    update_school,
)
from app.domain.roles import UserRole
from app.infrastructure.db.models import School, User, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import (
    get_current_school,
    get_current_school_id,
    get_current_school_memberships,
    require_authenticated,
    require_school_admin,
    require_school_roles,
)
from app.interfaces.api.v1.schemas.school import SchoolCreate, SchoolResponse, SchoolUpdate
from app.interfaces.api.v1.schemas.student import UserSchoolMembershipPayload

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("", response_model=list[SchoolResponse])
def get_schools(current_user: User = Depends(require_authenticated), db: Session = Depends(get_db)):
    schools = list_schools_for_user(db=db, user=current_user)
    return [serialize_school_response(school) for school in schools]


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
def create_school_endpoint(
    payload: SchoolCreate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school = create_school(db=db, payload=payload, creator_user_id=current_user.id)
    return serialize_school_response(school)


@router.get("/{school_id}", response_model=SchoolResponse)
def get_school(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    school: School = Depends(get_current_school),
    _: list[UserSchoolRole] = Depends(get_current_school_memberships),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    return serialize_school_response(school)


@router.put("/{school_id}", response_model=SchoolResponse, dependencies=[Depends(require_school_roles([UserRole.admin]))])
def update_school_endpoint(
    school_id: int,
    payload: SchoolUpdate,
    selected_school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    school = get_school_by_id(db=db, school_id=school_id)
    updated_school = update_school(db=db, school=school, payload=payload)
    return serialize_school_response(updated_school)


@router.delete("/{school_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_school_roles([UserRole.admin]))])
def delete_school_endpoint(
    school_id: int,
    selected_school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    if selected_school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path school id must match X-School-Id")
    school = get_school_by_id(db=db, school_id=school_id)
    delete_school(db=db, school=school)


@router.post("/{school_id}/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_school_admin)])
def associate_user_with_school(school_id: int, payload: UserSchoolMembershipPayload, db: Session = Depends(get_db)):
    add_user_school_role(db=db, school_id=school_id, user_id=payload.user_id, role=payload.role.value)
    return {"message": "User associated to school"}


@router.delete("/{school_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_school_admin)])
def deassociate_user_from_school(school_id: int, user_id: int, db: Session = Depends(get_db)):
    remove_user_school_roles(db=db, school_id=school_id, user_id=user_id)
