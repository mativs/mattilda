from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.roles import UserRole
from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class SchoolMemberAssignment(BaseModel):
    user_id: int
    roles: list[UserRole]


class SchoolCreate(BaseModel):
    name: str
    slug: str
    is_active: bool = True
    members: list[SchoolMemberAssignment] = Field(default_factory=list)


class SchoolUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    is_active: bool | None = None
    members: list[SchoolMemberAssignment] | None = None


class SchoolMemberResponse(BaseModel):
    user_id: int
    email: str
    roles: list[UserRole]


class SchoolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    members: list[SchoolMemberResponse]


class SchoolListResponse(BaseModel):
    items: list[SchoolResponse]
    pagination: PaginationMeta


class SchoolFinancialSummaryResponse(BaseModel):
    class RelevantInvoiceSummary(BaseModel):
        invoice_id: int
        student_id: int
        student_name: str
        period: str
        due_date: date
        total_amount: Decimal
        paid_amount: Decimal
        pending_amount: Decimal
        days_overdue: int

    class RelevantInvoiceBuckets(BaseModel):
        overdue_90_plus: list["SchoolFinancialSummaryResponse.RelevantInvoiceSummary"]
        top_pending_open: list["SchoolFinancialSummaryResponse.RelevantInvoiceSummary"]
        due_soon_7_days: list["SchoolFinancialSummaryResponse.RelevantInvoiceSummary"]

    total_billed_amount: Decimal
    total_charged_amount: Decimal
    total_paid_amount: Decimal
    total_pending_amount: Decimal
    student_count: int
    relevant_invoices: RelevantInvoiceBuckets


class SchoolInvoiceGenerationTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ReconciliationFindingResponse(BaseModel):
    id: int
    run_id: int
    school_id: int
    check_code: str
    severity: str
    entity_type: str | None
    entity_id: int | None
    message: str
    details_json: dict | None
    created_at: datetime
    updated_at: datetime


class ReconciliationRunResponse(BaseModel):
    id: int
    school_id: int
    triggered_by_user_id: int | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    summary_json: dict | None
    created_at: datetime
    updated_at: datetime


class ReconciliationRunListResponse(BaseModel):
    items: list[ReconciliationRunResponse]
    pagination: PaginationMeta


class ReconciliationRunDetailResponse(BaseModel):
    run: ReconciliationRunResponse
    findings: list[ReconciliationFindingResponse]


class ReconciliationRunTaskResponse(BaseModel):
    task_id: str
    run_id: int
    status: str
    message: str
