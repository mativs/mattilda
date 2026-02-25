from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.roles import UserRole


class StudentBase(BaseModel):
    first_name: str
    last_name: str
    external_id: str | None = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    external_id: str | None = None


class StudentResponse(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class StudentAssociateUserPayload(BaseModel):
    user_id: int


class StudentAssociateSchoolPayload(BaseModel):
    school_id: int


class UserSchoolMembershipPayload(BaseModel):
    user_id: int
    role: UserRole
