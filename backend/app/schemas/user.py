"""用户管理相关 Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.database import UserRole


class UserListItemResponse(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    items: list[UserListItemResponse]
    total: int
    skip: int
    limit: int


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default=UserRole.MEMBER.value)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResetPasswordRequest(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class UserBatchStatusRequest(BaseModel):
    user_ids: list[str] = Field(min_length=1)
    is_active: bool


class UserBatchDeleteRequest(BaseModel):
    user_ids: list[str] = Field(min_length=1)
