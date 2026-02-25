from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.roles import UserRole


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
