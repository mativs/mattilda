from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.application.errors import ConflictError, NotFoundError
from app.domain.charge_enums import ChargeStatus
from app.domain.invoice_status import InvoiceStatus
from app.domain.roles import UserRole
from app.infrastructure.db.models import Charge, Invoice, Payment, School, Student, StudentSchool, User, UserSchoolRole
from app.infrastructure.logging import get_logger
from app.interfaces.api.v1.schemas.school import SchoolCreate, SchoolUpdate

logger = get_logger(__name__)


def _build_member_map(school: School) -> list[dict]:
    grouped: dict[int, dict] = {}
    for membership in school.members:
        if membership.user.deleted_at is not None:
            continue
        if membership.user_id not in grouped:
            grouped[membership.user_id] = {
                "user_id": membership.user_id,
                "email": membership.user.email,
                "roles": [],
            }
        grouped[membership.user_id]["roles"].append(UserRole(membership.role))
    return list(grouped.values())


def serialize_school_response(school: School) -> dict:
    return {
        "id": school.id,
        "name": school.name,
        "slug": school.slug,
        "is_active": school.is_active,
        "created_at": school.created_at,
        "updated_at": school.updated_at,
        "members": _build_member_map(school),
    }


def _replace_memberships(db: Session, school: School, members_payload: list) -> None:
    db.execute(delete(UserSchoolRole).where(UserSchoolRole.school_id == school.id))
    if not members_payload:
        return

    user_ids = [member.user_id for member in members_payload]
    existing_users = db.execute(select(User).where(User.id.in_(user_ids), User.deleted_at.is_(None))).scalars().all()
    existing_by_id = {user.id: user for user in existing_users}
    missing_user_ids = sorted(set(user_ids) - set(existing_by_id))
    if missing_user_ids:
        raise NotFoundError(f"Users not found: {missing_user_ids}")

    memberships: list[UserSchoolRole] = []
    for member in members_payload:
        for role in member.roles:
            memberships.append(
                UserSchoolRole(
                    user_id=member.user_id,
                    school_id=school.id,
                    role=role.value,
                )
            )
    db.add_all(memberships)


def get_school_by_id(db: Session, school_id: int) -> School | None:
    return (
        db.execute(
            select(School)
            .where(School.id == school_id, School.deleted_at.is_(None))
            .options(joinedload(School.members).joinedload(UserSchoolRole.user))
        )
        .unique()
        .scalar_one_or_none()
    )


def list_schools_for_user(db: Session, user: User) -> list[School]:
    query = (
        select(School)
        .join(UserSchoolRole, UserSchoolRole.school_id == School.id)
        .where(UserSchoolRole.user_id == user.id, School.deleted_at.is_(None))
        .options(joinedload(School.members).joinedload(UserSchoolRole.user))
        .order_by(School.id)
    )
    return list(db.execute(query).unique().scalars().all())


def create_school(db: Session, payload: SchoolCreate, creator_user_id: int) -> School:
    existing_slug = db.execute(select(School).where(School.slug == payload.slug)).scalar_one_or_none()
    if existing_slug is not None:
        raise ConflictError("School slug already exists")

    school = School(name=payload.name, slug=payload.slug, is_active=payload.is_active)
    db.add(school)
    db.flush()
    _replace_memberships(db=db, school=school, members_payload=payload.members)
    creator_is_member = db.execute(
        select(UserSchoolRole).where(UserSchoolRole.user_id == creator_user_id, UserSchoolRole.school_id == school.id)
    ).scalar_one_or_none()
    if creator_is_member is None:
        db.add(UserSchoolRole(user_id=creator_user_id, school_id=school.id, role=UserRole.admin.value))
    db.commit()
    db.refresh(school)
    return get_school_by_id(db=db, school_id=school.id)  # type: ignore[return-value]


def update_school(db: Session, school: School, payload: SchoolUpdate) -> School:
    if payload.slug is not None and payload.slug != school.slug:
        existing_slug = db.execute(select(School).where(School.slug == payload.slug)).scalar_one_or_none()
        if existing_slug is not None:
            raise ConflictError("School slug already exists")
        school.slug = payload.slug
    if payload.name is not None:
        school.name = payload.name
    if payload.is_active is not None:
        school.is_active = payload.is_active
    if payload.members is not None:
        _replace_memberships(db=db, school=school, members_payload=payload.members)

    db.commit()
    db.refresh(school)
    return get_school_by_id(db=db, school_id=school.id)  # type: ignore[return-value]


def delete_school(db: Session, school: School) -> None:
    school.deleted_at = datetime.now(timezone.utc)
    school.is_active = False
    db.commit()


def add_user_school_role(db: Session, school_id: int, user_id: int, role: str) -> UserSchoolRole:
    school = db.execute(select(School).where(School.id == school_id, School.deleted_at.is_(None))).scalar_one_or_none()
    if school is None:
        raise NotFoundError("School not found")

    user = db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")

    existing = db.execute(
        select(UserSchoolRole).where(
            UserSchoolRole.school_id == school_id,
            UserSchoolRole.user_id == user_id,
            UserSchoolRole.role == role,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Membership already exists")

    membership = UserSchoolRole(school_id=school_id, user_id=user_id, role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def remove_user_school_roles(db: Session, school_id: int, user_id: int) -> None:
    memberships = (
        db.execute(
            select(UserSchoolRole).where(UserSchoolRole.school_id == school_id, UserSchoolRole.user_id == user_id)
        )
        .scalars()
        .all()
    )
    if not memberships:
        raise NotFoundError("Membership not found")
    for membership in memberships:
        db.delete(membership)
    db.commit()


def get_school_financial_summary(db: Session, *, school_id: int) -> dict:
    billed_total = db.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status == InvoiceStatus.open,
        )
    ).scalar_one()
    charged_total = db.execute(
        select(func.coalesce(func.sum(Charge.amount), 0)).where(
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
            Charge.status != ChargeStatus.cancelled,
            Charge.amount > Decimal("0.00"),
        )
    ).scalar_one()
    paid_total = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.school_id == school_id,
            Payment.deleted_at.is_(None),
        )
    ).scalar_one()
    pending_total = db.execute(
        select(func.coalesce(func.sum(Charge.amount), 0)).where(
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.unpaid,
        )
    ).scalar_one()
    student_count = db.execute(
        select(func.count(func.distinct(Student.id)))
        .select_from(StudentSchool)
        .join(Student, Student.id == StudentSchool.student_id)
        .where(StudentSchool.school_id == school_id, Student.deleted_at.is_(None))
    ).scalar_one()
    payment_totals = (
        select(
            Payment.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("paid_amount"),
        )
        .where(
            Payment.school_id == school_id,
            Payment.deleted_at.is_(None),
            Payment.invoice_id.is_not(None),
        )
        .group_by(Payment.invoice_id)
        .subquery()
    )
    open_invoice_rows = db.execute(
        select(
            Invoice.id.label("invoice_id"),
            Invoice.student_id.label("student_id"),
            Student.first_name.label("first_name"),
            Student.last_name.label("last_name"),
            Invoice.period.label("period"),
            Invoice.due_date.label("due_date"),
            Invoice.total_amount.label("total_amount"),
            func.coalesce(payment_totals.c.paid_amount, 0).label("paid_amount"),
        )
        .join(Student, Student.id == Invoice.student_id)
        .outerjoin(payment_totals, payment_totals.c.invoice_id == Invoice.id)
        .where(
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status == InvoiceStatus.open,
        )
        .order_by(Invoice.id.desc())
    ).all()
    today = date.today()
    relevant_base: list[dict] = []
    for row in open_invoice_rows:
        total_amount = Decimal(row.total_amount).quantize(Decimal("0.01"))
        paid_amount = Decimal(row.paid_amount).quantize(Decimal("0.01"))
        pending_amount = (total_amount - paid_amount).quantize(Decimal("0.01"))
        if pending_amount <= Decimal("0.00"):
            continue
        days_overdue = max((today - row.due_date).days, 0)
        relevant_base.append(
            {
                "invoice_id": row.invoice_id,
                "student_id": row.student_id,
                "student_name": f"{row.first_name} {row.last_name}".strip(),
                "period": row.period,
                "due_date": row.due_date,
                "total_amount": total_amount,
                "paid_amount": paid_amount,
                "pending_amount": pending_amount,
                "days_overdue": days_overdue,
            }
        )
    overdue_90_plus = [item for item in relevant_base if item["days_overdue"] >= 90]
    top_pending_open = sorted(
        relevant_base,
        key=lambda item: (
            item["pending_amount"] * Decimal("-1"),
            item["due_date"],
            item["invoice_id"],
        ),
    )[:5]
    due_soon_threshold = today + timedelta(days=7)
    due_soon_7_days = [
        item
        for item in relevant_base
        if today <= item["due_date"] <= due_soon_threshold
    ]

    summary = {
        "total_billed_amount": Decimal(billed_total).quantize(Decimal("0.01")),
        "total_charged_amount": Decimal(charged_total).quantize(Decimal("0.01")),
        "total_paid_amount": Decimal(paid_total).quantize(Decimal("0.01")),
        "total_pending_amount": Decimal(pending_total).quantize(Decimal("0.01")),
        "student_count": int(student_count),
        "relevant_invoices": {
            "overdue_90_plus": overdue_90_plus,
            "top_pending_open": top_pending_open,
            "due_soon_7_days": due_soon_7_days,
        },
    }
    logger.info(
        "school_financial_summary_computed",
        school_id=school_id,
        total_billed_amount=str(summary["total_billed_amount"]),
        total_charged_amount=str(summary["total_charged_amount"]),
        total_paid_amount=str(summary["total_paid_amount"]),
        total_pending_amount=str(summary["total_pending_amount"]),
        student_count=summary["student_count"],
        relevant_overdue_90_count=len(overdue_90_plus),
        relevant_top_pending_count=len(top_pending_open),
        relevant_due_soon_count=len(due_soon_7_days),
    )
    return summary
