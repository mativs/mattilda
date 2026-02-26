from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.errors import NotFoundError
from app.domain.charge_enums import ChargeStatus
from app.infrastructure.db.models import Charge, FeeDefinition, Student, StudentSchool
from app.interfaces.api.v1.schemas.charge import ChargeCreate, ChargeUpdate


def serialize_charge_response(charge: Charge) -> dict:
    return {
        "id": charge.id,
        "school_id": charge.school_id,
        "student_id": charge.student_id,
        "fee_definition_id": charge.fee_definition_id,
        "invoice_id": charge.invoice_id,
        "origin_invoice_id": charge.origin_invoice_id,
        "description": charge.description,
        "amount": charge.amount,
        "period": charge.period,
        "due_date": charge.due_date,
        "charge_type": charge.charge_type,
        "status": charge.status,
        "created_at": charge.created_at,
        "updated_at": charge.updated_at,
        "student": {
            "id": charge.student.id,
            "first_name": charge.student.first_name,
            "last_name": charge.student.last_name,
        },
    }


def get_charge_by_id(db: Session, charge_id: int, school_id: int) -> Charge | None:
    return db.execute(
        select(Charge).where(
            Charge.id == charge_id,
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def get_student_in_school(db: Session, student_id: int, school_id: int) -> Student:
    student = db.execute(
        select(Student)
        .join(StudentSchool, StudentSchool.student_id == Student.id)
        .where(
            Student.id == student_id,
            StudentSchool.school_id == school_id,
            Student.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if student is None:
        raise NotFoundError("Student not found")
    return student


def get_fee_definition_in_school(db: Session, fee_definition_id: int, school_id: int) -> FeeDefinition:
    fee_definition = db.execute(
        select(FeeDefinition).where(
            FeeDefinition.id == fee_definition_id,
            FeeDefinition.school_id == school_id,
            FeeDefinition.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if fee_definition is None:
        raise NotFoundError("Fee definition not found")
    return fee_definition


def create_charge(db: Session, school_id: int, payload: ChargeCreate) -> Charge:
    get_student_in_school(db=db, student_id=payload.student_id, school_id=school_id)
    if payload.fee_definition_id is not None:
        get_fee_definition_in_school(db=db, fee_definition_id=payload.fee_definition_id, school_id=school_id)
    charge = Charge(
        school_id=school_id,
        student_id=payload.student_id,
        fee_definition_id=payload.fee_definition_id,
        description=payload.description,
        amount=payload.amount,
        period=payload.period,
        due_date=payload.due_date,
        charge_type=payload.charge_type,
        status=payload.status,
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge


def update_charge(db: Session, charge: Charge, payload: ChargeUpdate) -> Charge:
    next_student_id = payload.student_id if payload.student_id is not None else charge.student_id
    if payload.student_id is not None:
        get_student_in_school(db=db, student_id=next_student_id, school_id=charge.school_id)
    if payload.fee_definition_id is not None:
        get_fee_definition_in_school(db=db, fee_definition_id=payload.fee_definition_id, school_id=charge.school_id)

    if payload.student_id is not None:
        charge.student_id = payload.student_id
    if payload.fee_definition_id is not None:
        charge.fee_definition_id = payload.fee_definition_id
    if payload.description is not None:
        charge.description = payload.description
    if payload.amount is not None:
        charge.amount = payload.amount
    if payload.period is not None:
        charge.period = payload.period
    if payload.due_date is not None:
        charge.due_date = payload.due_date
    if payload.charge_type is not None:
        charge.charge_type = payload.charge_type
    if payload.status is not None:
        charge.status = payload.status

    db.commit()
    db.refresh(charge)
    return charge


def delete_charge(db: Session, charge: Charge) -> None:
    charge.deleted_at = datetime.now(timezone.utc)
    charge.status = ChargeStatus.cancelled
    db.commit()


def get_unbilled_charges_for_student(db: Session, school_id: int, student_id: int) -> tuple[list[Charge], Decimal]:
    charges = list(
        db.execute(
            select(Charge)
            .where(
                Charge.school_id == school_id,
                Charge.student_id == student_id,
                Charge.status == ChargeStatus.unbilled,
                Charge.deleted_at.is_(None),
            )
            .order_by(Charge.due_date, Charge.id)
        )
        .scalars()
        .all()
    )
    total = sum((charge.amount for charge in charges), Decimal("0.00"))
    return charges, total
