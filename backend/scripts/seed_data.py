from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.security_service import hash_password
from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.fee_recurrence import FeeRecurrence
from app.domain.invoice_status import InvoiceStatus
from app.domain.roles import UserRole
from app.infrastructure.db.models import (
    Charge,
    FeeDefinition,
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
    debt_created_at: datetime,
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
        debt_created_at=debt_created_at,
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


def create_payment_if_missing(
    db: Session,
    *,
    school_id: int,
    student_id: int,
    invoice_id: int | None,
    amount: Decimal,
    paid_at: datetime,
    method: str,
) -> Payment:
    existing = db.execute(
        select(Payment).where(
            Payment.school_id == school_id,
            Payment.student_id == student_id,
            Payment.invoice_id == invoice_id,
            Payment.amount == amount,
            Payment.paid_at == paid_at,
            Payment.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    payment = Payment(
        school_id=school_id,
        student_id=student_id,
        invoice_id=invoice_id,
        amount=amount,
        paid_at=paid_at,
        method=method,
    )
    db.add(payment)
    db.flush()
    return payment


def _add_months(base_date: date, months: int) -> date:
    year_offset, month_index = divmod((base_date.month - 1) + months, 12)
    return date(base_date.year + year_offset, month_index + 1, 1)


def build_recent_period_starts(*, anchor_period: date, count: int) -> list[date]:
    oldest_offset = -(count - 1)
    return [_add_months(anchor_period, oldest_offset + index) for index in range(count)]


def _period_label(period_start: date) -> str:
    return f"{period_start.year:04d}-{period_start.month:02d}"


def _month_date(period_start: date, day: int) -> date:
    safe_day = min(day, 28)
    return date(period_start.year, period_start.month, safe_day)


def _month_datetime(period_start: date, day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(period_start.year, period_start.month, min(day, 28), hour, minute, tzinfo=timezone.utc)


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
    payment_methods = ["transfer", "cash", "card"]

    for index, period_start in enumerate(previous_periods):
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
            debt_created_at=issued_at,
            due_date=due_date,
            charge_type=ChargeType.fee,
            status=ChargeStatus.paid,
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
        charge.status = ChargeStatus.paid
        charge.invoice_id = invoice.id
        charge.origin_charge_id = None
        create_payment_if_missing(
            db=db,
            school_id=school.id,
            student_id=student.id,
            invoice_id=invoice.id,
            amount=invoice.total_amount,
            paid_at=datetime(period_start.year, period_start.month, 12, 12, 0, tzinfo=timezone.utc),
            method=payment_methods[index % len(payment_methods)],
        )

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
        debt_created_at=datetime(current_period.year, current_period.month, 1, 9, 0, tzinfo=timezone.utc),
        due_date=current_due_date,
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )

    partial_amount = (monthly_amount / Decimal("2")).quantize(Decimal("0.01"))
    partial_charge = create_charge_if_missing(
        db=db,
        school_id=school.id,
        student_id=student.id,
        fee_definition_id=monthly_fee.id,
        description=f"{monthly_fee.name} {current_label} (partial paid)",
        amount=partial_amount,
        period=current_label,
        debt_created_at=datetime(current_period.year, current_period.month, 1, 9, 0, tzinfo=timezone.utc),
        due_date=current_due_date,
        charge_type=ChargeType.fee,
        status=ChargeStatus.paid,
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
    partial_charge.status = ChargeStatus.paid
    partial_charge.invoice_id = open_invoice.id
    partial_charge.origin_charge_id = None
    create_payment_if_missing(
        db=db,
        school_id=school.id,
        student_id=student.id,
        invoice_id=open_invoice.id,
        amount=(open_invoice.total_amount / Decimal("2")).quantize(Decimal("0.01")),
        paid_at=datetime(current_period.year, current_period.month, 8, 12, 0, tzinfo=timezone.utc),
        method=payment_methods[0],
    )


def _attach_invoice_snapshot(db: Session, *, invoice: Invoice, charges: list[Charge]) -> None:
    for charge in charges:
        if charge.invoice_id != invoice.id:
            charge.invoice_id = invoice.id
        create_invoice_item_if_missing(
            db=db,
            invoice_id=invoice.id,
            charge_id=charge.id,
            description=charge.description,
            amount=charge.amount,
            charge_type=charge.charge_type,
        )
    invoice.total_amount = sum((charge.amount for charge in charges), Decimal("0.00"))


def seed_tc_lab_fixtures(db: Session, *, admin: User) -> None:
    """
    Seed deterministic manual fixtures for TC-01..TC-15 under tc-lab school.
    """
    tc_school = create_school_if_missing(db=db, name="TC Lab", slug="tc-lab")
    create_membership_if_missing(db=db, user_id=admin.id, school_id=tc_school.id, role=UserRole.admin)
    tc_monthly_fee = create_fee_if_missing(
        db=db,
        school_id=tc_school.id,
        name="TC Fee",
        amount=Decimal("100.00"),
        recurrence=FeeRecurrence.monthly,
    )

    # Mapping:
    # TC-01..TC-06 -> payment allocation baselines (open invoices)
    # TC-07..TC-10 -> interest generation baselines
    # TC-11..TC-13 -> overpayment/negative/overdue payment baselines
    # TC-14..TC-15 -> repeated invoice generation baselines
    tc_anchor = date.today().replace(day=1)
    payable_month = _add_months(tc_anchor, 1)
    overdue_month = _add_months(tc_anchor, -2)
    recent_past_month = _add_months(tc_anchor, -1)

    payable_period = _period_label(payable_month)
    overdue_period = _period_label(overdue_month)
    recent_past_period = _period_label(recent_past_month)

    payable_due_date = _month_date(payable_month, 10)
    overdue_due_date = _month_date(overdue_month, 10)

    tc_student_names: dict[int, tuple[str, str]] = {
        1: ("TC01", "FullPaymentOnTime"),
        2: ("TC02", "FullPaymentMultipleCharges"),
        3: ("TC03", "NoPaymentInvoiceStaysOpen"),
        4: ("TC04", "SimplePartialPayment"),
        5: ("TC05", "PartialAcrossMultipleCharges"),
        6: ("TC06", "PartialExactBoundary"),
        7: ("TC07", "OverdueFeeGeneratesInterest"),
        8: ("TC08", "InterestDeltaOnSecondGeneration"),
        9: ("TC09", "NoInterestOnInterestCharge"),
        10: ("TC10", "PaidFeeUnpaidInterestNoCompound"),
        11: ("TC11", "OverpaymentCreatesNegativeCarry"),
        12: ("TC12", "NegativeChargeReducesPayment"),
        13: ("TC13", "OverdueInvoicePaymentCreatesCredit"),
        14: ("TC14", "InvoiceGeneratedTwiceSamePeriod"),
        15: ("TC15", "InvoiceTwiceWithNewCharge"),
    }

    for tc in range(1, 16):
        code = f"TC-{tc:02d}"
        first_name, last_name = tc_student_names[tc]
        student = create_student_if_missing(
            db=db,
            first_name=first_name,
            last_name=last_name,
            external_id=f"{code}-STU",
        )
        associate_student_school_if_missing(db=db, student_id=student.id, school_id=tc_school.id)

        if tc == 1:
            charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-01 fee",
                amount=Decimal("100.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[charge])

        if tc == 2:
            charge_a = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-02 fee",
                amount=Decimal("100.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            charge_b = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=None,
                description="TC-02 penalty",
                amount=Decimal("50.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 2),
                due_date=payable_due_date,
                charge_type=ChargeType.penalty,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("150.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[charge_a, charge_b])

        if tc == 3:
            charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-03 fee",
                amount=Decimal("100.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[charge])

        if tc == 4:
            charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-04 fee",
                amount=Decimal("100.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[charge])

        if tc == 5:
            charges = [
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=tc_monthly_fee.id,
                    description="TC-05 charge A",
                    amount=Decimal("100.00"),
                    period=payable_period,
                    debt_created_at=_month_datetime(payable_month, 1),
                    due_date=payable_due_date,
                    charge_type=ChargeType.fee,
                    status=ChargeStatus.unpaid,
                ),
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=tc_monthly_fee.id,
                    description="TC-05 charge B",
                    amount=Decimal("50.00"),
                    period=payable_period,
                    debt_created_at=_month_datetime(payable_month, 2),
                    due_date=payable_due_date,
                    charge_type=ChargeType.fee,
                    status=ChargeStatus.unpaid,
                ),
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=None,
                    description="TC-05 charge C",
                    amount=Decimal("30.00"),
                    period=payable_period,
                    debt_created_at=_month_datetime(payable_month, 3),
                    due_date=payable_due_date,
                    charge_type=ChargeType.penalty,
                    status=ChargeStatus.unpaid,
                ),
            ]
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("180.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=charges)

        if tc == 6:
            charges = [
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=tc_monthly_fee.id,
                    description="TC-06 charge A",
                    amount=Decimal("100.00"),
                    period=payable_period,
                    debt_created_at=_month_datetime(payable_month, 1),
                    due_date=payable_due_date,
                    charge_type=ChargeType.fee,
                    status=ChargeStatus.unpaid,
                ),
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=tc_monthly_fee.id,
                    description="TC-06 charge B",
                    amount=Decimal("100.00"),
                    period=payable_period,
                    debt_created_at=_month_datetime(payable_month, 2),
                    due_date=payable_due_date,
                    charge_type=ChargeType.fee,
                    status=ChargeStatus.unpaid,
                ),
            ]
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("200.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=charges)

        if tc == 7:
            create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-07 overdue fee",
                amount=Decimal("100.00"),
                period=overdue_period,
                debt_created_at=_month_datetime(overdue_month, 1),
                due_date=overdue_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )

        if tc == 8:
            base_fee = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-08 overdue fee",
                amount=Decimal("100.00"),
                period=overdue_period,
                debt_created_at=_month_datetime(overdue_month, 1),
                due_date=_month_date(overdue_month, 1),
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            existing_interest = db.execute(
                select(Charge).where(
                    Charge.school_id == tc_school.id,
                    Charge.student_id == student.id,
                    Charge.description == "TC-08 existing interest",
                    Charge.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if existing_interest is None:
                db.add(
                    Charge(
                        school_id=tc_school.id,
                        student_id=student.id,
                        fee_definition_id=None,
                        invoice_id=None,
                        origin_charge_id=base_fee.id,
                        description="TC-08 existing interest",
                        amount=Decimal("2.00"),
                        period=recent_past_period,
                        debt_created_at=_month_datetime(recent_past_month, 1),
                        due_date=_month_date(recent_past_month, 1),
                        charge_type=ChargeType.interest,
                        status=ChargeStatus.unpaid,
                    )
                )

        if tc == 9:
            base_fee = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-09 base fee paid",
                amount=Decimal("100.00"),
                period=overdue_period,
                debt_created_at=_month_datetime(overdue_month, 1),
                due_date=overdue_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.paid,
            )
            base_invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=overdue_period,
                issued_at=_month_datetime(overdue_month, 1),
                due_date=overdue_due_date,
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.closed,
            )
            _attach_invoice_snapshot(db=db, invoice=base_invoice, charges=[base_fee])
            create_payment_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                invoice_id=base_invoice.id,
                amount=Decimal("100.00"),
                paid_at=_month_datetime(overdue_month, 12, 12, 0),
                method="transfer",
            )
            existing_interest = db.execute(
                select(Charge).where(
                    Charge.school_id == tc_school.id,
                    Charge.student_id == student.id,
                    Charge.description == "TC-09 overdue interest",
                    Charge.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if existing_interest is not None:
                existing_interest.origin_charge_id = base_fee.id
            else:
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=None,
                    description="TC-09 overdue interest",
                    amount=Decimal("10.00"),
                    period=overdue_period,
                    debt_created_at=_month_datetime(overdue_month, 1),
                    due_date=overdue_due_date,
                    charge_type=ChargeType.interest,
                    status=ChargeStatus.unpaid,
                ).origin_charge_id = base_fee.id

        if tc == 10:
            fee_charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-10 fee paid",
                amount=Decimal("100.00"),
                period=recent_past_period,
                debt_created_at=_month_datetime(recent_past_month, 1),
                due_date=_month_date(recent_past_month, 10),
                charge_type=ChargeType.fee,
                status=ChargeStatus.paid,
            )
            fee_invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=recent_past_period,
                issued_at=_month_datetime(recent_past_month, 1),
                due_date=_month_date(recent_past_month, 10),
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.closed,
            )
            _attach_invoice_snapshot(db=db, invoice=fee_invoice, charges=[fee_charge])
            create_payment_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                invoice_id=fee_invoice.id,
                amount=Decimal("100.00"),
                paid_at=_month_datetime(recent_past_month, 12, 12, 0),
                method="transfer",
            )
            existing_interest = db.execute(
                select(Charge).where(
                    Charge.school_id == tc_school.id,
                    Charge.student_id == student.id,
                    Charge.description == "TC-10 interest unpaid",
                    Charge.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if existing_interest is not None:
                existing_interest.origin_charge_id = fee_charge.id
            else:
                create_charge_if_missing(
                    db=db,
                    school_id=tc_school.id,
                    student_id=student.id,
                    fee_definition_id=None,
                    description="TC-10 interest unpaid",
                    amount=Decimal("10.00"),
                    period=recent_past_period,
                    debt_created_at=_month_datetime(recent_past_month, 11),
                    due_date=_month_date(recent_past_month, 11),
                    charge_type=ChargeType.interest,
                    status=ChargeStatus.unpaid,
                ).origin_charge_id = fee_charge.id

        if tc == 11:
            charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-11 fee",
                amount=Decimal("100.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[charge])

        if tc == 12:
            fee_charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-12 fee",
                amount=Decimal("100.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            carry_charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=None,
                description="TC-12 carry",
                amount=Decimal("-20.00"),
                period=payable_period,
                debt_created_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                charge_type=ChargeType.penalty,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=payable_period,
                issued_at=_month_datetime(payable_month, 1),
                due_date=payable_due_date,
                total_amount=Decimal("80.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[fee_charge, carry_charge])

        if tc == 13:
            charge = create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-13 overdue fee",
                amount=Decimal("100.00"),
                period=overdue_period,
                debt_created_at=_month_datetime(overdue_month, 1),
                due_date=overdue_due_date,
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )
            invoice = create_invoice_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                period=overdue_period,
                issued_at=_month_datetime(overdue_month, 1),
                due_date=overdue_due_date,
                total_amount=Decimal("100.00"),
                status=InvoiceStatus.open,
            )
            _attach_invoice_snapshot(db=db, invoice=invoice, charges=[charge])

        if tc == 14:
            create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-14 fee",
                amount=Decimal("100.00"),
                period=recent_past_period,
                debt_created_at=_month_datetime(recent_past_month, 1),
                due_date=_month_date(recent_past_month, 10),
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )

        if tc == 15:
            create_charge_if_missing(
                db=db,
                school_id=tc_school.id,
                student_id=student.id,
                fee_definition_id=tc_monthly_fee.id,
                description="TC-15 charge A",
                amount=Decimal("100.00"),
                period=recent_past_period,
                debt_created_at=_month_datetime(recent_past_month, 1),
                due_date=_month_date(recent_past_month, 10),
                charge_type=ChargeType.fee,
                status=ChargeStatus.unpaid,
            )


def seed_reconciliation_lab_fixtures(db: Session, *, admin: User) -> None:
    """
    Seed manual reconciliation demo fixtures under reconciliation-lab school.

    Triggered checks:
    - invoice_total_mismatch
    - interest_invalid_origin
    - invoice_open_with_sufficient_payments
    - duplicate_payment_window
    - paid_charge_without_payment_evidence
    """

    recon_school = create_school_if_missing(db=db, name="Reconciliation Lab", slug="reconciliation-lab")
    create_membership_if_missing(db=db, user_id=admin.id, school_id=recon_school.id, role=UserRole.admin)
    today_anchor = date.today().replace(day=1)

    mismatch_student = create_student_if_missing(
        db=db,
        first_name="RECON-01",
        last_name="Mismatch",
        external_id="RECON-01-STU",
    )
    associate_student_school_if_missing(db=db, student_id=mismatch_student.id, school_id=recon_school.id)
    mismatch_period = f"{today_anchor.year:04d}-{today_anchor.month:02d}-RM"
    mismatch_due = _month_date(today_anchor, 20)
    mismatch_charge = create_charge_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=mismatch_student.id,
        fee_definition_id=None,
        description="RECON-01 charge for invoice mismatch",
        amount=Decimal("80.00"),
        period=mismatch_period,
        debt_created_at=_month_datetime(today_anchor, 1),
        due_date=mismatch_due,
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    mismatch_invoice = create_invoice_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=mismatch_student.id,
        period=mismatch_period,
        issued_at=_month_datetime(today_anchor, 1),
        due_date=mismatch_due,
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.open,
    )
    mismatch_charge.invoice_id = mismatch_invoice.id
    create_invoice_item_if_missing(
        db=db,
        invoice_id=mismatch_invoice.id,
        charge_id=mismatch_charge.id,
        description=mismatch_charge.description,
        amount=Decimal("80.00"),
        charge_type=mismatch_charge.charge_type,
    )
    mismatch_invoice.total_amount = Decimal("100.00")

    invalid_interest_student = create_student_if_missing(
        db=db,
        first_name="RECON-02",
        last_name="InterestOrigin",
        external_id="RECON-02-STU",
    )
    associate_student_school_if_missing(db=db, student_id=invalid_interest_student.id, school_id=recon_school.id)
    invalid_interest_period = f"{today_anchor.year:04d}-{today_anchor.month:02d}-RI"
    create_charge_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=invalid_interest_student.id,
        fee_definition_id=None,
        description="RECON-02 invalid interest origin",
        amount=Decimal("10.00"),
        period=invalid_interest_period,
        debt_created_at=_month_datetime(today_anchor, 2),
        due_date=_month_date(today_anchor, 18),
        charge_type=ChargeType.interest,
        status=ChargeStatus.unpaid,
    )

    open_paid_student = create_student_if_missing(
        db=db,
        first_name="RECON-03",
        last_name="OpenPaid",
        external_id="RECON-03-STU",
    )
    associate_student_school_if_missing(db=db, student_id=open_paid_student.id, school_id=recon_school.id)
    open_paid_period = f"{today_anchor.year:04d}-{today_anchor.month:02d}-RO"
    open_paid_due = _month_date(today_anchor, 22)
    open_paid_charge = create_charge_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=open_paid_student.id,
        fee_definition_id=None,
        description="RECON-03 open invoice fully paid charge",
        amount=Decimal("120.00"),
        period=open_paid_period,
        debt_created_at=_month_datetime(today_anchor, 3),
        due_date=open_paid_due,
        charge_type=ChargeType.fee,
        status=ChargeStatus.unpaid,
    )
    open_paid_invoice = create_invoice_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=open_paid_student.id,
        period=open_paid_period,
        issued_at=_month_datetime(today_anchor, 3),
        due_date=open_paid_due,
        total_amount=Decimal("120.00"),
        status=InvoiceStatus.open,
    )
    open_paid_charge.invoice_id = open_paid_invoice.id
    create_invoice_item_if_missing(
        db=db,
        invoice_id=open_paid_invoice.id,
        charge_id=open_paid_charge.id,
        description=open_paid_charge.description,
        amount=Decimal("120.00"),
        charge_type=open_paid_charge.charge_type,
    )
    open_paid_invoice.total_amount = Decimal("120.00")
    create_payment_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=open_paid_student.id,
        invoice_id=open_paid_invoice.id,
        amount=Decimal("120.00"),
        paid_at=_month_datetime(today_anchor, 5, 10, 0),
        method="transfer",
    )

    duplicate_student = create_student_if_missing(
        db=db,
        first_name="RECON-04",
        last_name="DuplicatePayment",
        external_id="RECON-04-STU",
    )
    associate_student_school_if_missing(db=db, student_id=duplicate_student.id, school_id=recon_school.id)
    duplicate_base = _month_datetime(today_anchor, 6, 11, 0)
    create_payment_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=duplicate_student.id,
        invoice_id=None,
        amount=Decimal("25.00"),
        paid_at=duplicate_base,
        method="card",
    )
    create_payment_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=duplicate_student.id,
        invoice_id=None,
        amount=Decimal("25.00"),
        paid_at=duplicate_base + timedelta(seconds=30),
        method="card",
    )

    paid_wo_payment_student = create_student_if_missing(
        db=db,
        first_name="RECON-05",
        last_name="PaidWithoutPayment",
        external_id="RECON-05-STU",
    )
    associate_student_school_if_missing(db=db, student_id=paid_wo_payment_student.id, school_id=recon_school.id)
    paid_wo_payment_period = f"{today_anchor.year:04d}-{today_anchor.month:02d}-RP"
    create_charge_if_missing(
        db=db,
        school_id=recon_school.id,
        student_id=paid_wo_payment_student.id,
        fee_definition_id=None,
        description="RECON-05 paid charge without payment trail",
        amount=Decimal("90.00"),
        period=paid_wo_payment_period,
        debt_created_at=_month_datetime(today_anchor, 7),
        due_date=_month_date(today_anchor, 25),
        charge_type=ChargeType.fee,
        status=ChargeStatus.paid,
    )


def seed_visibility_lab_fixtures(db: Session, *, admin: User, teacher: User, student_user: User) -> None:
    """
    Seed role-visibility fixtures under visibility-lab school.

    Scenario:
    - one teacher associated to two students (can see both)
    - one student user associated only to itself (can see only one)
    """
    visibility_school = create_school_if_missing(db=db, name="Visibility Lab", slug="visibility-lab")
    create_membership_if_missing(db=db, user_id=admin.id, school_id=visibility_school.id, role=UserRole.admin)
    create_membership_if_missing(db=db, user_id=teacher.id, school_id=visibility_school.id, role=UserRole.teacher)
    create_membership_if_missing(db=db, user_id=student_user.id, school_id=visibility_school.id, role=UserRole.student)

    student_a = create_student_if_missing(
        db=db,
        first_name="VIS-01",
        last_name="TeacherVisibleA",
        external_id="VIS-01-STU",
    )
    student_b = create_student_if_missing(
        db=db,
        first_name="VIS-02",
        last_name="TeacherVisibleB",
        external_id="VIS-02-STU",
    )
    associate_student_school_if_missing(db=db, student_id=student_a.id, school_id=visibility_school.id)
    associate_student_school_if_missing(db=db, student_id=student_b.id, school_id=visibility_school.id)

    # Teacher can see both students in this school.
    associate_user_student_if_missing(db=db, user_id=teacher.id, student_id=student_a.id)
    associate_user_student_if_missing(db=db, user_id=teacher.id, student_id=student_b.id)
    # Student user can only see itself (student A) in this school.
    associate_user_student_if_missing(db=db, user_id=student_user.id, student_id=student_a.id)


def main() -> None:
    db = SessionLocal()
    try:
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
        student_user = create_user_if_missing(
            db=db,
            email="student@example.com",
            password="student123",
            profile=("Student", "User"),
        )

        seed_tc_lab_fixtures(db=db, admin=admin)
        seed_reconciliation_lab_fixtures(db=db, admin=admin)
        seed_visibility_lab_fixtures(db=db, admin=admin, teacher=teacher, student_user=student_user)

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
