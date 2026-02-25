from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.domain.roles import UserRole


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


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    roles: list[UserRole]
    is_active: bool = True
    profile: UserProfileCreate


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    roles: list[UserRole] | None = None
    is_active: bool | None = None
    profile: UserProfileUpdate | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    roles: list[UserRole]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse
