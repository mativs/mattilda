from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.charge_enums import ChargeStatus, ChargeType
from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class ChargeBase(BaseModel):
    student_id: int
    fee_definition_id: int | None = None
    description: str
    amount: Decimal
    period: str | None = None
    due_date: date
    charge_type: ChargeType
    status: ChargeStatus = ChargeStatus.unbilled


class ChargeCreate(ChargeBase):
    pass


class ChargeUpdate(BaseModel):
    student_id: int | None = None
    fee_definition_id: int | None = None
    description: str | None = None
    amount: Decimal | None = None
    period: str | None = None
    due_date: date | None = None
    charge_type: ChargeType | None = None
    status: ChargeStatus | None = None


class ChargeStudentRef(BaseModel):
    id: int
    first_name: str
    last_name: str


class ChargeResponse(ChargeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    invoice_id: int | None = None
    origin_invoice_id: int | None = None
    created_at: datetime
    updated_at: datetime
    student: ChargeStudentRef


class ChargeListResponse(BaseModel):
    items: list[ChargeResponse]
    pagination: PaginationMeta


class StudentUnbilledChargesResponse(BaseModel):
    items: list[ChargeResponse] = Field(default_factory=list)
    total_unbilled_amount: Decimal = Decimal("0.00")
