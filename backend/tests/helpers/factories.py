from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.roles import UserRole
from app.infrastructure.db.models import Charge, School, Student, StudentSchool, User, UserProfile, UserSchoolRole, UserStudent


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
    status: ChargeStatus = ChargeStatus.unbilled,
    period: str | None = None,
    fee_definition_id: int | None = None,
) -> Charge:
    charge = Charge(
        school_id=school_id,
        student_id=student_id,
        fee_definition_id=fee_definition_id,
        description=description,
        amount=Decimal(amount),
        period=period,
        due_date=due_date,
        charge_type=charge_type,
        status=status,
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge
