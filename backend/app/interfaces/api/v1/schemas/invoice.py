from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.charge_enums import ChargeType
from app.domain.invoice_status import InvoiceStatus
from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class InvoiceStudentRef(BaseModel):
    id: int
    first_name: str
    last_name: str


class InvoiceSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    student_id: int
    period: str
    issued_at: datetime
    due_date: date
    total_amount: Decimal
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
    student: InvoiceStudentRef


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    charge_id: int
    description: str
    amount: Decimal
    charge_type: ChargeType
    created_at: datetime
    updated_at: datetime


class InvoiceDetailResponse(InvoiceSummaryResponse):
    items: list[InvoiceItemResponse]


class InvoiceListResponse(BaseModel):
    items: list[InvoiceSummaryResponse]
    pagination: PaginationMeta
