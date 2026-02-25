from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.roles import UserRole
from app.interfaces.api.v1.schemas.pagination import PaginationMeta


class UserProfileBase(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    address: str | None = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    address: str | None = None


class UserProfileResponse(UserProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class UserSchoolRolesResponse(BaseModel):
    school_id: int
    school_name: str
    roles: list[UserRole]


class UserStudentResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    external_id: str | None = None
    school_ids: list[int] = Field(default_factory=list)


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    is_active: bool = True
    profile: UserProfileCreate


class UserSchoolRoleAssociationUpdate(BaseModel):
    school_id: int
    role: UserRole


class UserAssociationsPartialUpdate(BaseModel):
    school_roles: list[UserSchoolRoleAssociationUpdate] = Field(default_factory=list)


class UserAssociationsUpdate(BaseModel):
    add: UserAssociationsPartialUpdate = Field(default_factory=UserAssociationsPartialUpdate)
    remove: UserAssociationsPartialUpdate = Field(default_factory=UserAssociationsPartialUpdate)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None
    profile: UserProfileUpdate | None = None
    associations: UserAssociationsUpdate | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse
    schools: list[UserSchoolRolesResponse] = Field(default_factory=list)
    students: list[UserStudentResponse] = Field(default_factory=list)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    pagination: PaginationMeta
