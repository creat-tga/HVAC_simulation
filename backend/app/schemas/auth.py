"""User and account management schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str = "user"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=200)
    email: str | None = Field(None, max_length=200)
    full_name: str | None = Field(None, max_length=200)


class UserUpdate(BaseModel):
    email: str | None = Field(None, max_length=200)
    full_name: str | None = Field(None, max_length=200)
    password: str | None = Field(None, min_length=6, max_length=200)


class AdminUserUpdate(BaseModel):
    role: Literal["admin", "user"] | None = None
    status: Literal["pending", "active", "disabled"] | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None
    full_name: str | None
    role: str
    status: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserActivityLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    target: str | None
    detail: str | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
