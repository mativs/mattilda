from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.roles import UserRole
from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class StudentBase(BaseModel):
    first_name: str
    last_name: str
    external_id: str | None = None


class StudentCreate(StudentBase):
    pass


class StudentAssociationsPartialUpdate(BaseModel):
    user_ids: list[int] = Field(default_factory=list)
    school_ids: list[int] = Field(default_factory=list)


class StudentAssociationsUpdate(BaseModel):
    add: StudentAssociationsPartialUpdate = Field(default_factory=StudentAssociationsPartialUpdate)
    remove: StudentAssociationsPartialUpdate = Field(default_factory=StudentAssociationsPartialUpdate)


class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    external_id: str | None = None
    associations: StudentAssociationsUpdate | None = None


class StudentUserRef(BaseModel):
    id: int
    name: str
    email: str


class StudentSchoolRef(BaseModel):
    id: int
    name: str
    slug: str


class StudentResponse(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    user_ids: list[int] = Field(default_factory=list)
    school_ids: list[int] = Field(default_factory=list)
    users: list[StudentUserRef] = Field(default_factory=list)
    schools: list[StudentSchoolRef] = Field(default_factory=list)


class StudentAssociateUserPayload(BaseModel):
    user_id: int


class StudentAssociateSchoolPayload(BaseModel):
    school_id: int


class UserSchoolMembershipPayload(BaseModel):
    user_id: int
    role: UserRole


class StudentListResponse(BaseModel):
    items: list[StudentResponse]
    pagination: PaginationMeta
