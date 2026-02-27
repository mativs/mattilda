from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.domain.roles import UserRole
from app.infrastructure.db.models import (
    Charge,
    Invoice,
    InvoiceItem,
    Payment,
    School,
    Student,
    StudentSchool,
    User,
    UserProfile,
    UserSchoolRole,
    UserStudent,
)


def create_user(db: Session, email: str, password: str = "pass123", is_active: bool = True) -> User:
    user = User(email=email, hashed_password=hash_password(password), is_active=is_active)
    user.profile = UserProfile(first_name="Test", last_name="User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_school(db: Session, name: str, slug: str, is_active: bool = True) -> School:
    school = School(name=name, slug=slug, is_active=is_active)
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def add_membership(db: Session, user_id: int, school_id: int, role: UserRole) -> UserSchoolRole:
    membership = UserSchoolRole(user_id=user_id, school_id=school_id, role=role.value)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def create_student(db: Session, first_name: str, last_name: str, external_id: str | None = None) -> Student:
    student = Student(first_name=first_name, last_name=last_name, external_id=external_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def link_student_school(db: Session, student_id: int, school_id: int) -> StudentSchool:
    link = StudentSchool(student_id=student_id, school_id=school_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def link_user_student(db: Session, user_id: int, student_id: int) -> UserStudent:
    link = UserStudent(user_id=user_id, student_id=student_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def create_charge(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    description: str,
    amount: str,
    due_date: date,
    charge_type: ChargeType = ChargeType.fee,
    status: ChargeStatus = ChargeStatus.unpaid,
    period: str | None = None,
    debt_created_at: datetime | None = None,
    fee_definition_id: int | None = None,
    invoice_id: int | None = None,
    origin_charge_id: int | None = None,
) -> Charge:
    charge = Charge(
        school_id=school_id,
        student_id=student_id,
        fee_definition_id=fee_definition_id,
        description=description,
        amount=Decimal(amount),
        period=period,
        debt_created_at=debt_created_at or datetime.combine(due_date, datetime.min.time(), tzinfo=timezone.utc),
        due_date=due_date,
        charge_type=charge_type,
        status=status,
        invoice_id=invoice_id,
        origin_charge_id=origin_charge_id,
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge


def create_invoice(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    period: str,
    issued_at: datetime,
    due_date: date,
    total_amount: str,
    status: InvoiceStatus = InvoiceStatus.open,
) -> Invoice:
    invoice = Invoice(
        school_id=school_id,
        student_id=student_id,
        period=period,
        issued_at=issued_at,
        due_date=due_date,
        total_amount=Decimal(total_amount),
        status=status,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_invoice_item(
    db: Session,
    *,
    invoice_id: int,
    charge_id: int,
    description: str,
    amount: str,
    charge_type: ChargeType = ChargeType.fee,
) -> InvoiceItem:
    item = InvoiceItem(
        invoice_id=invoice_id,
        charge_id=charge_id,
        description=description,
        amount=Decimal(amount),
        charge_type=charge_type,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_payment(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    amount: str,
    paid_at: datetime,
    method: str = "transfer",
    invoice_id: int | None = None,
) -> Payment:
    payment = Payment(
        school_id=school_id,
        student_id=student_id,
        invoice_id=invoice_id,
        amount=Decimal(amount),
        paid_at=paid_at,
        method=method,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def persist_entities(db: Session, *entities: object) -> None:
    db.add_all(list(entities))
    db.commit()


def persist_entity(db: Session, entity: object) -> None:
    db.add(entity)
    db.commit()


def commit_session(db: Session) -> None:
    db.commit()


def refresh_entity(db: Session, entity: object) -> None:
    db.refresh(entity)


def get_entity_by_id(db: Session, model: type, entity_id: int):
    return db.get(model, entity_id)


def list_from_query(db: Session, query: Select):
    return list(db.execute(query).scalars().all())


def list_charges_for_student(db: Session, *, student_id: int) -> list[Charge]:
    return list_from_query(db, select(Charge).where(Charge.student_id == student_id))


def list_charges_for_invoice(db: Session, *, invoice_id: int) -> list[Charge]:
    return list_from_query(db, select(Charge).where(Charge.invoice_id == invoice_id))


def list_interest_charges_for_student(db: Session, *, student_id: int) -> list[Charge]:
    return list_from_query(
        db,
        select(Charge).where(
            Charge.student_id == student_id,
            Charge.charge_type == ChargeType.interest,
        ),
    )


def list_interest_charges_for_origin(db: Session, *, origin_charge_id: int) -> list[Charge]:
    return list_from_query(
        db,
        select(Charge).where(
            Charge.origin_charge_id == origin_charge_id,
            Charge.charge_type == ChargeType.interest,
            Charge.deleted_at.is_(None),
        ),
    )


def list_negative_unpaid_carry_for_student(db: Session, *, student_id: int) -> list[Charge]:
    return list_from_query(
        db,
        select(Charge).where(
            Charge.student_id == student_id,
            Charge.invoice_id.is_(None),
            Charge.amount < Decimal("0.00"),
            Charge.status == ChargeStatus.unpaid,
            Charge.deleted_at.is_(None),
        ),
    )


def get_negative_charge_for_invoice(db: Session, *, invoice_id: int) -> Charge:
    return db.execute(
        select(Charge).where(Charge.invoice_id == invoice_id, Charge.amount < 0, Charge.deleted_at.is_(None))
    ).scalar_one()


def list_invoice_items_for_invoice(db: Session, *, invoice_id: int) -> list[InvoiceItem]:
    return list_from_query(db, select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id))


def list_reconciliation_runs(db: Session, *, school_id: int) -> list:
    from app.application.services.reconciliation_service import list_reconciliation_runs_query

    return list_from_query(db, list_reconciliation_runs_query(school_id=school_id))
