from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class PaymentCreate(BaseModel):
    student_id: int
    invoice_id: int
    amount: Decimal
    paid_at: datetime
    method: str


class PaymentStudentRef(BaseModel):
    id: int
    first_name: str
    last_name: str


class PaymentInvoiceRef(BaseModel):
    id: int
    period: str
    status: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    student_id: int
    invoice_id: int | None = None
    amount: Decimal
    paid_at: datetime
    method: str
    created_at: datetime
    updated_at: datetime
    student: PaymentStudentRef
    invoice: PaymentInvoiceRef | None = None


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    pagination: PaginationMeta
