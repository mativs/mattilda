from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.pagination_service import paginate_scalars
from app.application.services.charge_service import get_student_in_school, get_unbilled_charges_for_student, serialize_charge_response
from app.application.services.student_service import (
    associate_student_school,
    associate_user_student,
    create_student_for_school,
    deassociate_student_school,
    deassociate_user_student,
    delete_student,
    get_student_by_id,
    get_visible_student_for_user,
    serialize_student_response,
    update_student,
)
from app.domain.roles import UserRole
from app.infrastructure.db.models import Student, StudentSchool, User, UserSchoolRole, UserStudent
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.dependencies.auth import get_current_school_id, get_current_school_memberships, require_authenticated, require_school_admin
from app.interfaces.api.v1.dependencies.pagination import get_pagination_params
from app.interfaces.api.v1.schemas.pagination import PaginationParams
from app.interfaces.api.v1.schemas.charge import StudentUnbilledChargesResponse
from app.interfaces.api.v1.schemas.student import (
    StudentAssociateSchoolPayload,
    StudentAssociateUserPayload,
    StudentCreate,
    StudentListResponse,
    StudentResponse,
    StudentUpdate,
)

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=StudentListResponse)
def get_students(
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    pagination: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    if any(link.role == UserRole.admin.value for link in memberships):
        base_query = (
            select(Student)
            .join(StudentSchool, StudentSchool.student_id == Student.id)
            .where(StudentSchool.school_id == school_id, Student.deleted_at.is_(None))
            .order_by(Student.id)
        )
    else:
        base_query = (
            select(Student)
            .join(StudentSchool, StudentSchool.student_id == Student.id)
            .join(UserStudent, UserStudent.student_id == Student.id)
            .where(
                StudentSchool.school_id == school_id,
                UserStudent.user_id == current_user.id,
                Student.deleted_at.is_(None),
            )
            .order_by(Student.id)
        )
    students, meta = paginate_scalars(
        db=db,
        base_query=base_query,
        offset=pagination.offset,
        limit=pagination.limit,
        search=pagination.search,
        search_columns=[Student.first_name, Student.last_name, Student.external_id],
    )
    return {"items": [serialize_student_response(student) for student in students], "pagination": meta}


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_school_admin)])
def create_student_endpoint(payload: StudentCreate, school_id: int = Depends(get_current_school_id), db: Session = Depends(get_db)):
    student = create_student_for_school(db=db, payload=payload, school_id=school_id)
    return serialize_student_response(student)


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    school_id: int = Depends(get_current_school_id),
    current_user: User = Depends(require_authenticated),
    memberships: list[UserSchoolRole] = Depends(get_current_school_memberships),
    db: Session = Depends(get_db),
):
    student = get_visible_student_for_user(
        db=db,
        student_id=student_id,
        school_id=school_id,
        user_id=current_user.id,
        is_admin=any(link.role == UserRole.admin.value for link in memberships),
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return serialize_student_response(student)


@router.get(
    "/{student_id}/charges/unbilled",
    response_model=StudentUnbilledChargesResponse,
    dependencies=[Depends(require_school_admin)],
)
def get_student_unbilled_charges(
    student_id: int,
    school_id: int = Depends(get_current_school_id),
    db: Session = Depends(get_db),
):
    student = get_student_in_school(db=db, student_id=student_id, school_id=school_id)
    charges, total = get_unbilled_charges_for_student(db=db, school_id=school_id, student_id=student.id)
    return {"items": [serialize_charge_response(charge) for charge in charges], "total_unbilled_amount": total}


@router.put("/{student_id}", response_model=StudentResponse, dependencies=[Depends(require_school_admin)])
def update_student_endpoint(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    student = get_student_by_id(db=db, student_id=student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    updated = update_student(db=db, student=student, payload=payload)
    return serialize_student_response(updated)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_school_admin)])
def delete_student_endpoint(student_id: int, db: Session = Depends(get_db)):
    student = get_student_by_id(db=db, student_id=student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    delete_student(db=db, student=student)


@router.post("/{student_id}/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_school_admin)])
def associate_user(student_id: int, payload: StudentAssociateUserPayload, db: Session = Depends(get_db)):
    associate_user_student(db=db, user_id=payload.user_id, student_id=student_id)
    return {"message": "User associated with student"}


@router.delete("/{student_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_school_admin)])
def deassociate_user(student_id: int, user_id: int, db: Session = Depends(get_db)):
    deassociate_user_student(db=db, user_id=user_id, student_id=student_id)


@router.post("/{student_id}/schools", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_school_admin)])
def associate_school(student_id: int, payload: StudentAssociateSchoolPayload, db: Session = Depends(get_db)):
    associate_student_school(db=db, student_id=student_id, school_id=payload.school_id)
    return {"message": "Student associated with school"}


@router.delete("/{student_id}/schools/{school_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_school_admin)])
def deassociate_school(student_id: int, school_id: int, db: Session = Depends(get_db)):
    deassociate_student_school(db=db, student_id=student_id, school_id=school_id)
