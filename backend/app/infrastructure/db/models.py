from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.domain.fee_recurrence import FeeRecurrence
from app.domain.invoice_status import InvoiceStatus
from app.infrastructure.db.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )


class TenantScopedMixin:
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)


class User(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["UserProfile"] = relationship(
        "UserProfile", back_populates="user", uselist=False, cascade="all,delete"
    )
    school_memberships: Mapped[list["UserSchoolRole"]] = relationship(
        "UserSchoolRole",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    student_links: Mapped[list["UserStudent"]] = relationship(
        "UserStudent",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class School(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["UserSchoolRole"]] = relationship(
        "UserSchoolRole",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    dummy_records: Mapped[list["DummyRecord"]] = relationship(
        "DummyRecord",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    student_links: Mapped[list["StudentSchool"]] = relationship(
        "StudentSchool",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    fee_definitions: Mapped[list["FeeDefinition"]] = relationship(
        "FeeDefinition",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    charges: Mapped[list["Charge"]] = relationship(
        "Charge",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="school",
        cascade="all, delete-orphan",
    )


class UserSchoolRole(TimestampMixin, Base):
    __tablename__ = "user_school_roles"
    __table_args__ = (UniqueConstraint("user_id", "school_id", "role", name="uq_user_school_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    user: Mapped[User] = relationship("User", back_populates="school_memberships")
    school: Mapped[School] = relationship("School", back_populates="members")


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="profile")


class Student(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    user_links: Mapped[list["UserStudent"]] = relationship(
        "UserStudent",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    school_links: Mapped[list["StudentSchool"]] = relationship(
        "StudentSchool",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    charges: Mapped[list["Charge"]] = relationship(
        "Charge",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="student",
        cascade="all, delete-orphan",
    )


class UserStudent(TimestampMixin, Base):
    __tablename__ = "user_students"
    __table_args__ = (UniqueConstraint("user_id", "student_id", name="uq_user_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)

    user: Mapped[User] = relationship("User", back_populates="student_links")
    student: Mapped[Student] = relationship("Student", back_populates="user_links")


class StudentSchool(TimestampMixin, Base):
    __tablename__ = "student_schools"
    __table_args__ = (UniqueConstraint("student_id", "school_id", name="uq_student_school"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    student: Mapped[Student] = relationship("Student", back_populates="school_links")
    school: Mapped[School] = relationship("School", back_populates="student_links")


class DummyRecord(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "dummy_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    school: Mapped[School] = relationship("School", back_populates="dummy_records")


class FeeDefinition(SoftDeleteMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "fee_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    recurrence: Mapped[FeeRecurrence] = mapped_column(
        Enum(FeeRecurrence, name="fee_recurrence"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    school: Mapped[School] = relationship("School", back_populates="fee_definitions")
    charges: Mapped[list["Charge"]] = relationship("Charge", back_populates="fee_definition")


class Charge(SoftDeleteMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "charges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_definition_id: Mapped[int | None] = mapped_column(
        ForeignKey("fee_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    origin_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    charge_type: Mapped[ChargeType] = mapped_column(Enum(ChargeType, name="charge_type"), nullable=False, index=True)
    status: Mapped[ChargeStatus] = mapped_column(
        Enum(ChargeStatus, name="charge_status"),
        nullable=False,
        default=ChargeStatus.unbilled,
        index=True,
    )

    school: Mapped[School] = relationship("School", back_populates="charges")
    student: Mapped[Student] = relationship("Student", back_populates="charges")
    fee_definition: Mapped[FeeDefinition | None] = relationship("FeeDefinition", back_populates="charges")
    invoice: Mapped["Invoice | None"] = relationship(
        "Invoice",
        foreign_keys=[invoice_id],
        back_populates="charges",
    )
    origin_invoice: Mapped["Invoice | None"] = relationship("Invoice", foreign_keys=[origin_invoice_id])


class Invoice(SoftDeleteMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"), nullable=False, index=True
    )

    school: Mapped[School] = relationship("School", back_populates="invoices")
    student: Mapped[Student] = relationship("Student", back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    charges: Mapped[list["Charge"]] = relationship("Charge", foreign_keys=[Charge.invoice_id], back_populates="invoice")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )


class InvoiceItem(TimestampMixin, Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_id: Mapped[int] = mapped_column(ForeignKey("charges.id", ondelete="RESTRICT"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    charge_type: Mapped[ChargeType] = mapped_column(Enum(ChargeType, name="charge_type"), nullable=False, index=True)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="items")
    charge: Mapped[Charge] = relationship("Charge")


class Payment(SoftDeleteMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    school: Mapped[School] = relationship("School", back_populates="payments")
    student: Mapped[Student] = relationship("Student", back_populates="payments")
    invoice: Mapped[Invoice | None] = relationship("Invoice", back_populates="payments")
