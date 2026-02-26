from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.fee_recurrence import FeeRecurrence
from app.domain.invoice_status import InvoiceStatus
from app.domain.roles import UserRole
from app.infrastructure.db.models import Charge, FeeDefinition, Invoice, InvoiceItem, School, Student, StudentSchool, User, UserProfile, UserSchoolRole, UserStudent
from app.infrastructure.db.session import SessionLocal

HISTORY_PERIODS = 6
ANCHOR_PERIOD = date(2026, 3, 1)


def create_user_if_missing(
    db: Session,
    email: str,
    password: str,
    profile: tuple[str, str],
) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        return existing

    user = User(email=email, hashed_password=hash_password(password), is_active=True)
    user.profile = UserProfile(first_name=profile[0], last_name=profile[1])
    db.add(user)
    db.flush()
    return user


def create_school_if_missing(db: Session, name: str, slug: str) -> School:
    school = db.execute(select(School).where(School.slug == slug)).scalar_one_or_none()
    if school is not None:
        return school

    school = School(name=name, slug=slug, is_active=True)
    db.add(school)
    db.flush()
    return school


def create_membership_if_missing(db: Session, user_id: int, school_id: int, role: UserRole) -> None:
    existing = db.execute(
        select(UserSchoolRole).where(
            UserSchoolRole.user_id == user_id,
            UserSchoolRole.school_id == school_id,
            UserSchoolRole.role == role.value,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(UserSchoolRole(user_id=user_id, school_id=school_id, role=role.value))


def create_student_if_missing(db: Session, first_name: str, last_name: str, external_id: str) -> Student:
    student = db.execute(select(Student).where(Student.external_id == external_id, Student.deleted_at.is_(None))).scalar_one_or_none()
    if student is not None:
        return student
    student = Student(first_name=first_name, last_name=last_name, external_id=external_id)
    db.add(student)
    db.flush()
    return student


def associate_student_school_if_missing(db: Session, student_id: int, school_id: int) -> None:
    existing = db.execute(
        select(StudentSchool).where(StudentSchool.student_id == student_id, StudentSchool.school_id == school_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(StudentSchool(student_id=student_id, school_id=school_id))


def associate_user_student_if_missing(db: Session, user_id: int, student_id: int) -> None:
    existing = db.execute(
        select(UserStudent).where(UserStudent.user_id == user_id, UserStudent.student_id == student_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(UserStudent(user_id=user_id, student_id=student_id))


def create_fee_if_missing(
    db: Session,
    *,
    school_id: int,
    name: str,
    amount: Decimal,
    recurrence: FeeRecurrence,
    is_active: bool = True,
) -> FeeDefinition:
    existing = db.execute(
        select(FeeDefinition).where(
            FeeDefinition.school_id == school_id,
            FeeDefinition.name == name,
            FeeDefinition.recurrence == recurrence,
            FeeDefinition.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    fee = FeeDefinition(
        school_id=school_id,
        name=name,
        amount=amount,
        recurrence=recurrence,
        is_active=is_active,
    )
    db.add(fee)
    db.flush()
    return fee


def create_charge_if_missing(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    fee_definition_id: int | None,
    description: str,
    amount: Decimal,
    period: str | None,
    due_date: date,
    charge_type: ChargeType,
    status: ChargeStatus,
) -> Charge:
    existing = db.execute(
        select(Charge).where(
            Charge.school_id == school_id,
            Charge.student_id == student_id,
            Charge.description == description,
            Charge.due_date == due_date,
            Charge.charge_type == charge_type,
            Charge.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    charge = Charge(
        school_id=school_id,
        student_id=student_id,
        fee_definition_id=fee_definition_id,
        description=description,
        amount=amount,
        period=period,
        due_date=due_date,
        charge_type=charge_type,
        status=status,
    )
    db.add(charge)
    db.flush()
    return charge


def create_invoice_if_missing(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    period: str,
    issued_at: datetime,
    due_date: date,
    total_amount: Decimal,
    status: InvoiceStatus,
) -> Invoice:
    existing = db.execute(
        select(Invoice).where(
            Invoice.school_id == school_id,
            Invoice.student_id == student_id,
            Invoice.period == period,
            Invoice.status == status,
            Invoice.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    invoice = Invoice(
        school_id=school_id,
        student_id=student_id,
        period=period,
        issued_at=issued_at,
        due_date=due_date,
        total_amount=total_amount,
        status=status,
    )
    db.add(invoice)
    db.flush()
    return invoice


def create_invoice_item_if_missing(
    db: Session,
    *,
    invoice_id: int,
    charge_id: int,
    description: str,
    amount: Decimal,
    charge_type: ChargeType,
) -> InvoiceItem:
    existing = db.execute(
        select(InvoiceItem).where(
            InvoiceItem.invoice_id == invoice_id,
            InvoiceItem.charge_id == charge_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    item = InvoiceItem(
        invoice_id=invoice_id,
        charge_id=charge_id,
        description=description,
        amount=amount,
        charge_type=charge_type,
    )
    db.add(item)
    db.flush()
    return item


def _add_months(base_date: date, months: int) -> date:
    year_offset, month_index = divmod((base_date.month - 1) + months, 12)
    return date(base_date.year + year_offset, month_index + 1, 1)


def build_recent_period_starts(*, anchor_period: date, count: int) -> list[date]:
    oldest_offset = -(count - 1)
    return [_add_months(anchor_period, oldest_offset + index) for index in range(count)]


def _period_label(period_start: date) -> str:
    return f"{period_start.year:04d}-{period_start.month:02d}"


def seed_billing_history_for_student_school(
    db: Session,
    *,
    student: Student,
    school: School,
    monthly_fee: FeeDefinition,
    monthly_amount: Decimal,
    periods: list[date],
) -> None:
    previous_periods = periods[:-1]
    current_period = periods[-1]

    for period_start in previous_periods:
        period = _period_label(period_start)
        due_date = date(period_start.year, period_start.month, 10)
        issued_at = datetime(period_start.year, period_start.month, 1, 9, 0, tzinfo=timezone.utc)
        description = f"{monthly_fee.name} {period}"
        charge = create_charge_if_missing(
            db=db,
            school_id=school.id,
            student_id=student.id,
            fee_definition_id=monthly_fee.id,
            description=description,
            amount=monthly_amount,
            period=period,
            due_date=due_date,
            charge_type=ChargeType.fee,
            status=ChargeStatus.billed,
        )
        invoice = create_invoice_if_missing(
            db=db,
            school_id=school.id,
            student_id=student.id,
            period=period,
            issued_at=issued_at,
            due_date=due_date,
            total_amount=monthly_amount,
            status=InvoiceStatus.closed,
        )
        create_invoice_item_if_missing(
            db=db,
            invoice_id=invoice.id,
            charge_id=charge.id,
            description=charge.description,
            amount=charge.amount,
            charge_type=charge.charge_type,
        )
        invoice.total_amount = sum((item.amount for item in invoice.items), Decimal("0.00"))
        charge.status = ChargeStatus.billed
        charge.invoice_id = invoice.id
        charge.origin_invoice_id = invoice.id

    current_label = _period_label(current_period)
    current_due_date = date(current_period.year, current_period.month, 10)
    create_charge_if_missing(
        db=db,
        school_id=school.id,
        student_id=student.id,
        fee_definition_id=monthly_fee.id,
        description=f"{monthly_fee.name} {current_label} (pending)",
        amount=monthly_amount,
        period=current_label,
        due_date=current_due_date,
        charge_type=ChargeType.fee,
        status=ChargeStatus.unbilled,
    )

    partial_amount = (monthly_amount / Decimal("2")).quantize(Decimal("0.01"))
    partial_charge = create_charge_if_missing(
        db=db,
        school_id=school.id,
        student_id=student.id,
        fee_definition_id=monthly_fee.id,
        description=f"{monthly_fee.name} {current_label} (partial billed)",
        amount=partial_amount,
        period=current_label,
        due_date=current_due_date,
        charge_type=ChargeType.fee,
        status=ChargeStatus.billed,
    )
    open_invoice = create_invoice_if_missing(
        db=db,
        school_id=school.id,
        student_id=student.id,
        period=current_label,
        issued_at=datetime(current_period.year, current_period.month, 1, 9, 0, tzinfo=timezone.utc),
        due_date=current_due_date,
        total_amount=partial_amount,
        status=InvoiceStatus.open,
    )
    create_invoice_item_if_missing(
        db=db,
        invoice_id=open_invoice.id,
        charge_id=partial_charge.id,
        description=partial_charge.description,
        amount=partial_charge.amount,
        charge_type=partial_charge.charge_type,
    )
    open_invoice.total_amount = sum((item.amount for item in open_invoice.items), Decimal("0.00"))
    partial_charge.status = ChargeStatus.billed
    partial_charge.invoice_id = open_invoice.id
    partial_charge.origin_invoice_id = open_invoice.id


def main() -> None:
    db = SessionLocal()
    try:
        north_school = create_school_if_missing(db=db, name="North High", slug="north-high")
        south_school = create_school_if_missing(db=db, name="South High", slug="south-high")

        admin = create_user_if_missing(
            db=db,
            email="admin@example.com",
            password="admin123",
            profile=("Admin", "User"),
        )
        teacher = create_user_if_missing(
            db=db,
            email="teacher@example.com",
            password="teacher123",
            profile=("Teacher", "User"),
        )
        student = create_user_if_missing(
            db=db,
            email="student@example.com",
            password="student123",
            profile=("Student", "User"),
        )

        create_membership_if_missing(db=db, user_id=admin.id, school_id=north_school.id, role=UserRole.admin)
        create_membership_if_missing(db=db, user_id=admin.id, school_id=south_school.id, role=UserRole.admin)
        create_membership_if_missing(db=db, user_id=teacher.id, school_id=north_school.id, role=UserRole.teacher)
        create_membership_if_missing(db=db, user_id=teacher.id, school_id=south_school.id, role=UserRole.teacher)
        create_membership_if_missing(db=db, user_id=student.id, school_id=north_school.id, role=UserRole.student)

        child_one = create_student_if_missing(db=db, first_name="Alice", last_name="Student", external_id="STU-001")
        child_two = create_student_if_missing(db=db, first_name="Bob", last_name="Student", external_id="STU-002")

        associate_student_school_if_missing(db=db, student_id=child_one.id, school_id=north_school.id)
        associate_student_school_if_missing(db=db, student_id=child_two.id, school_id=north_school.id)
        associate_student_school_if_missing(db=db, student_id=child_two.id, school_id=south_school.id)
        associate_user_student_if_missing(db=db, user_id=student.id, student_id=child_one.id)
        associate_user_student_if_missing(db=db, user_id=student.id, student_id=child_two.id)
        associate_user_student_if_missing(db=db, user_id=teacher.id, student_id=child_two.id)

        north_monthly_fee = create_fee_if_missing(
            db=db,
            school_id=north_school.id,
            name="Cuota mensual",
            amount=Decimal("150.00"),
            recurrence=FeeRecurrence.monthly,
        )
        create_fee_if_missing(
            db=db,
            school_id=north_school.id,
            name="Matrícula",
            amount=Decimal("450.00"),
            recurrence=FeeRecurrence.annual,
        )
        south_monthly_fee = create_fee_if_missing(
            db=db,
            school_id=south_school.id,
            name="Cuota mensual",
            amount=Decimal("120.00"),
            recurrence=FeeRecurrence.monthly,
        )
        create_fee_if_missing(
            db=db,
            school_id=south_school.id,
            name="Materiales",
            amount=Decimal("95.00"),
            recurrence=FeeRecurrence.one_time,
        )
        periods = build_recent_period_starts(anchor_period=ANCHOR_PERIOD, count=HISTORY_PERIODS)
        for student_obj, school_obj, fee_obj, amount in [
            (child_one, north_school, north_monthly_fee, Decimal("150.00")),
            (child_two, north_school, north_monthly_fee, Decimal("150.00")),
            (child_two, south_school, south_monthly_fee, Decimal("120.00")),
        ]:
            seed_billing_history_for_student_school(
                db=db,
                student=student_obj,
                school=school_obj,
                monthly_fee=fee_obj,
                monthly_amount=amount,
                periods=periods,
            )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
