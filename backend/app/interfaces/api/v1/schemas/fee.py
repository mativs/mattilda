from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.fee_recurrence import FeeRecurrence
from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class FeeBase(BaseModel):
    name: str
    amount: Decimal
    recurrence: FeeRecurrence
    is_active: bool = True


class FeeCreate(FeeBase):
    pass


class FeeUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = None
    recurrence: FeeRecurrence | None = None
    is_active: bool | None = None


class FeeResponse(FeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime


class FeeListResponse(BaseModel):
    items: list[FeeResponse]
    pagination: PaginationMeta
