from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.models import Charge, Invoice, InvoiceItem, Payment


def _check_invoice_total_vs_items(db: Session, *, school_id: int) -> list[dict]:
    rows = db.execute(
        select(
            Invoice.id.label("invoice_id"),
            Invoice.total_amount.label("invoice_total"),
            func.coalesce(func.sum(InvoiceItem.amount), Decimal("0.00")).label("items_total"),
        )
        .outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .where(Invoice.school_id == school_id, Invoice.deleted_at.is_(None))
        .group_by(Invoice.id, Invoice.total_amount)
        .having(Invoice.total_amount != func.coalesce(func.sum(InvoiceItem.amount), Decimal("0.00")))
    ).all()
    return [
        {
            "check_code": "invoice_total_mismatch",
            "severity": "high",
            "entity_type": "invoice",
            "entity_id": row.invoice_id,
            "message": "Invoice total does not match sum of invoice items",
            "details_json": {"invoice_total": str(row.invoice_total), "items_total": str(row.items_total)},
        }
        for row in rows
    ]


def _check_orphan_unpaid_charges(db: Session, *, school_id: int, as_of: datetime) -> list[dict]:
    open_not_due_invoice_exists = (
        select(Invoice.id)
        .where(
            Invoice.school_id == school_id,
            Invoice.student_id == Charge.student_id,
            Invoice.status == InvoiceStatus.open,
            Invoice.deleted_at.is_(None),
            Invoice.due_date >= as_of.date(),
        )
        .exists()
    )
    rows = db.execute(
        select(Charge.id, Charge.student_id, Charge.due_date)
        .where(
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.unpaid,
            Charge.invoice_id.is_(None),
            Charge.due_date <= as_of.date(),
            open_not_due_invoice_exists,
        )
        .order_by(Charge.id)
    ).all()
    return [
        {
            "check_code": "orphan_unpaid_charge",
            "severity": "medium",
            "entity_type": "charge",
            "entity_id": row.id,
            "message": "Unpaid charge is not linked to any invoice while student has open not-due invoice",
            "details_json": {"student_id": row.student_id, "due_date": str(row.due_date)},
        }
        for row in rows
    ]


def _check_invoice_items_on_cancelled_charges_without_residual(db: Session, *, school_id: int) -> list[dict]:
    residual = aliased(Charge)
    rows = db.execute(
        select(InvoiceItem.id, InvoiceItem.invoice_id, InvoiceItem.charge_id)
        .join(Charge, Charge.id == InvoiceItem.charge_id)
        .outerjoin(
            residual,
            and_(
                residual.origin_charge_id == Charge.id,
                residual.deleted_at.is_(None),
                residual.school_id == school_id,
            ),
        )
        .where(
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.cancelled,
            residual.id.is_(None),
        )
        .order_by(InvoiceItem.id)
    ).all()
    return [
        {
            "check_code": "invoice_item_cancelled_charge_no_residual",
            "severity": "medium",
            "entity_type": "invoice_item",
            "entity_id": row.id,
            "message": "Invoice item points to cancelled charge without residual replacement",
            "details_json": {"invoice_id": row.invoice_id, "charge_id": row.charge_id},
        }
        for row in rows
    ]


def _check_interest_invalid_origin(db: Session, *, school_id: int) -> list[dict]:
    origin = aliased(Charge)
    rows = db.execute(
        select(Charge.id, Charge.origin_charge_id)
        .outerjoin(origin, origin.id == Charge.origin_charge_id)
        .where(
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
            Charge.charge_type == ChargeType.interest,
            or_(
                Charge.origin_charge_id.is_(None),
                origin.id.is_(None),
                origin.deleted_at.is_not(None),
                origin.status == ChargeStatus.cancelled,
            ),
        )
        .order_by(Charge.id)
    ).all()
    return [
        {
            "check_code": "interest_invalid_origin",
            "severity": "high",
            "entity_type": "charge",
            "entity_id": row.id,
            "message": "Interest charge has invalid origin charge",
            "details_json": {"origin_charge_id": row.origin_charge_id},
        }
        for row in rows
    ]


def _check_confirmed_payments_without_invoice_closure(db: Session, *, school_id: int) -> list[dict]:
    payment_totals = (
        select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), Decimal("0.00")).label("paid_total"))
        .where(Payment.school_id == school_id, Payment.deleted_at.is_(None), Payment.invoice_id.is_not(None))
        .group_by(Payment.invoice_id)
        .subquery()
    )
    rows = db.execute(
        select(Invoice.id, Invoice.total_amount, payment_totals.c.paid_total)
        .join(payment_totals, payment_totals.c.invoice_id == Invoice.id)
        .where(
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status == InvoiceStatus.open,
            payment_totals.c.paid_total >= Invoice.total_amount,
        )
        .order_by(Invoice.id)
    ).all()
    return [
        {
            "check_code": "invoice_open_with_sufficient_payments",
            "severity": "high",
            "entity_type": "invoice",
            "entity_id": row.id,
            "message": "Invoice remains open despite confirmed payments covering total amount",
            "details_json": {"invoice_total": str(row.total_amount), "paid_total": str(row.paid_total)},
        }
        for row in rows
    ]


def _check_unapplied_negative_charges(db: Session, *, school_id: int) -> list[dict]:
    payment_exists_for_invoice = (
        select(Payment.id)
        .where(
            Payment.school_id == school_id,
            Payment.deleted_at.is_(None),
            Payment.invoice_id == Charge.invoice_id,
        )
        .exists()
    )
    rows = db.execute(
        select(Charge.id, Charge.invoice_id, Charge.student_id, Charge.amount)
        .where(
            Charge.school_id == school_id,
            Charge.deleted_at.is_(None),
            Charge.status == ChargeStatus.unpaid,
            Charge.amount < Decimal("0.00"),
            Charge.invoice_id.is_not(None),
            payment_exists_for_invoice,
        )
        .order_by(Charge.id)
    ).all()
    return [
        {
            "check_code": "unapplied_negative_charge",
            "severity": "medium",
            "entity_type": "charge",
            "entity_id": row.id,
            "message": "Negative unpaid charge remains linked to invoice that already has payments",
            "details_json": {
                "invoice_id": row.invoice_id,
                "student_id": row.student_id,
                "amount": str(row.amount),
            },
        }
        for row in rows
    ]


def _check_duplicate_payments(db: Session, *, school_id: int, window_seconds: int = 60) -> list[dict]:
    p1 = aliased(Payment)
    p2 = aliased(Payment)
    rows = db.execute(
        select(
            p1.id.label("payment_id_a"),
            p2.id.label("payment_id_b"),
            p1.student_id.label("student_id"),
            p1.amount.label("amount"),
            p1.paid_at.label("paid_at_a"),
            p2.paid_at.label("paid_at_b"),
        )
        .join(
            p2,
            and_(
                p2.id > p1.id,
                p2.school_id == p1.school_id,
                p2.student_id == p1.student_id,
                p2.deleted_at.is_(None),
                p2.amount == p1.amount,
            ),
        )
        .where(
            p1.school_id == school_id,
            p1.deleted_at.is_(None),
            func.abs(func.extract("epoch", p2.paid_at - p1.paid_at)) <= window_seconds,
        )
        .order_by(p1.id, p2.id)
    ).all()
    return [
        {
            "check_code": "duplicate_payment_window",
            "severity": "high",
            "entity_type": "payment",
            "entity_id": row.payment_id_a,
            "message": "Potential duplicate payments detected in narrow time window",
            "details_json": {
                "payment_id_pair": [row.payment_id_a, row.payment_id_b],
                "student_id": row.student_id,
                "amount": str(row.amount),
                "paid_at_pair": [row.paid_at_a.isoformat(), row.paid_at_b.isoformat()],
                "window_seconds": window_seconds,
            },
        }
        for row in rows
    ]


def run_all_reconciliation_checks(db: Session, *, school_id: int, as_of: datetime | None = None) -> list[dict]:
    as_of = as_of or datetime.now(timezone.utc)
    findings: list[dict] = []
    findings.extend(_check_invoice_total_vs_items(db=db, school_id=school_id))
    findings.extend(_check_orphan_unpaid_charges(db=db, school_id=school_id, as_of=as_of))
    findings.extend(_check_invoice_items_on_cancelled_charges_without_residual(db=db, school_id=school_id))
    findings.extend(_check_interest_invalid_origin(db=db, school_id=school_id))
    findings.extend(_check_confirmed_payments_without_invoice_closure(db=db, school_id=school_id))
    findings.extend(_check_unapplied_negative_charges(db=db, school_id=school_id))
    findings.extend(_check_duplicate_payments(db=db, school_id=school_id))
    return findings
