from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.errors import ConflictError
from app.domain.fee_recurrence import FeeRecurrence
from app.infrastructure.db.models import FeeDefinition
from app.interfaces.api.v1.schemas.fee import FeeCreate, FeeUpdate


def serialize_fee_response(fee: FeeDefinition) -> dict:
    return {
        "id": fee.id,
        "school_id": fee.school_id,
        "name": fee.name,
        "amount": fee.amount,
        "recurrence": fee.recurrence,
        "is_active": fee.is_active,
        "created_at": fee.created_at,
        "updated_at": fee.updated_at,
    }


def get_fee_definition_by_id(db: Session, fee_id: int, school_id: int) -> FeeDefinition | None:
    return db.execute(
        select(FeeDefinition).where(
            FeeDefinition.id == fee_id,
            FeeDefinition.school_id == school_id,
            FeeDefinition.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def _get_fee_by_natural_key(db: Session, school_id: int, name: str, recurrence: FeeRecurrence) -> FeeDefinition | None:
    return db.execute(
        select(FeeDefinition).where(
            FeeDefinition.school_id == school_id,
            FeeDefinition.name == name,
            FeeDefinition.recurrence == recurrence,
            FeeDefinition.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def create_fee_definition(db: Session, school_id: int, payload: FeeCreate) -> FeeDefinition:
    existing = _get_fee_by_natural_key(db=db, school_id=school_id, name=payload.name, recurrence=payload.recurrence)
    if existing is not None:
        raise ConflictError("Fee definition already exists")

    fee = FeeDefinition(
        school_id=school_id,
        name=payload.name,
        amount=payload.amount,
        recurrence=payload.recurrence,
        is_active=payload.is_active,
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


def update_fee_definition(db: Session, fee: FeeDefinition, payload: FeeUpdate) -> FeeDefinition:
    next_name = payload.name if payload.name is not None else fee.name
    next_recurrence = payload.recurrence if payload.recurrence is not None else fee.recurrence
    if next_name != fee.name or next_recurrence != fee.recurrence:
        existing = _get_fee_by_natural_key(
            db=db,
            school_id=fee.school_id,
            name=next_name,
            recurrence=next_recurrence,
        )
        if existing is not None and existing.id != fee.id:
            raise ConflictError("Fee definition already exists")

    if payload.name is not None:
        fee.name = payload.name
    if payload.amount is not None:
        fee.amount = payload.amount
    if payload.recurrence is not None:
        fee.recurrence = payload.recurrence
    if payload.is_active is not None:
        fee.is_active = payload.is_active

    db.commit()
    db.refresh(fee)
    return fee


def delete_fee_definition(db: Session, fee: FeeDefinition) -> None:
    fee.deleted_at = datetime.now(timezone.utc)
    fee.is_active = False
    db.commit()
