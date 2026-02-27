from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.charge_enums import ChargeStatus
from app.infrastructure.cache.cache_service import delete_key, get_json, set_json
from app.infrastructure.db.models import Charge, Payment


def student_balance_cache_key(*, school_id: int, student_id: int) -> str:
    return f"student_balance:{school_id}:{student_id}"


def invalidate_student_balance_cache(*, school_id: int, student_id: int) -> None:
    delete_key(student_balance_cache_key(school_id=school_id, student_id=student_id))


def get_student_balance_snapshot(db: Session, *, school_id: int, student_id: int) -> dict[str, Decimal]:
    cache_key = student_balance_cache_key(school_id=school_id, student_id=student_id)
    cached = get_json(cache_key)
    if cached is not None:
        return {
            "total_charged_amount": Decimal(cached["total_charged_amount"]).quantize(Decimal("0.01")),
            "total_paid_amount": Decimal(cached["total_paid_amount"]).quantize(Decimal("0.01")),
            "total_unpaid_amount": Decimal(cached["total_unpaid_amount"]).quantize(Decimal("0.01")),
            "total_unpaid_debt_amount": Decimal(cached["total_unpaid_debt_amount"]).quantize(Decimal("0.01")),
            "total_unpaid_credit_amount": Decimal(cached["total_unpaid_credit_amount"]).quantize(Decimal("0.01")),
        }

    charged_total = db.execute(
        select(func.coalesce(func.sum(Charge.amount), 0)).where(
            Charge.school_id == school_id,
            Charge.student_id == student_id,
            Charge.deleted_at.is_(None),
            Charge.status != ChargeStatus.cancelled,
            Charge.amount > Decimal("0.00"),
        )
    ).scalar_one()
    unpaid_net_total = db.execute(
        select(func.coalesce(func.sum(Charge.amount), 0)).where(
            Charge.school_id == school_id,
            Charge.student_id == student_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.unpaid,
        )
    ).scalar_one()
    unpaid_debt_total = db.execute(
        select(func.coalesce(func.sum(Charge.amount), 0)).where(
            Charge.school_id == school_id,
            Charge.student_id == student_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.unpaid,
            Charge.amount > Decimal("0.00"),
        )
    ).scalar_one()
    unpaid_credit_raw = db.execute(
        select(func.coalesce(func.sum(Charge.amount), 0)).where(
            Charge.school_id == school_id,
            Charge.student_id == student_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.unpaid,
            Charge.amount < Decimal("0.00"),
        )
    ).scalar_one()
    paid_total = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.school_id == school_id,
            Payment.student_id == student_id,
            Payment.deleted_at.is_(None),
        )
    ).scalar_one()

    snapshot = {
        "total_unpaid_amount": Decimal(unpaid_net_total).quantize(Decimal("0.01")),
        "total_unpaid_debt_amount": Decimal(unpaid_debt_total).quantize(Decimal("0.01")),
        "total_unpaid_credit_amount": abs(Decimal(unpaid_credit_raw).quantize(Decimal("0.01"))),
        "total_charged_amount": Decimal(charged_total).quantize(Decimal("0.01")),
        "total_paid_amount": Decimal(paid_total).quantize(Decimal("0.01")),
    }
    set_json(
        cache_key,
        {
            "total_unpaid_amount": str(snapshot["total_unpaid_amount"]),
            "total_unpaid_debt_amount": str(snapshot["total_unpaid_debt_amount"]),
            "total_unpaid_credit_amount": str(snapshot["total_unpaid_credit_amount"]),
            "total_charged_amount": str(snapshot["total_charged_amount"]),
            "total_paid_amount": str(snapshot["total_paid_amount"]),
        },
        settings.student_balance_cache_ttl_seconds,
    )
    return snapshot
