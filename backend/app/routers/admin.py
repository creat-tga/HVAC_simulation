"""Admin user management and activity logs."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserActivityLog
from app.routers.auth import get_admin_user, get_current_user
from app.schemas.auth import (
    AdminUserUpdate,
    UserActivityLogResponse,
    UserResponse,
)

router = APIRouter(prefix="/admin", tags=["管理员"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    status_filter: Literal["all", "pending", "active", "disabled"] = Query("all", alias="status"),
    role_filter: Literal["all", "admin", "user"] = Query("all", alias="role"),
    keyword: str | None = None,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).order_by(User.created_at.desc())
    if status_filter != "all":
        stmt = stmt.where(User.status == status_filter)
    if role_filter != "all":
        stmt = stmt.where(User.role == role_filter)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(User.username.ilike(kw))
    return (await db.execute(stmt)).scalars().all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and (data.role == "user" or data.is_active is False or data.status == "disabled"):
        raise HTTPException(status_code=400, detail="不能修改自己的角色或禁用自己")
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status
        if data.status == "disabled":
            user.is_active = False
        elif data.status == "active":
            user.is_active = True
    if data.is_active is not None:
        user.is_active = data.is_active
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def admin_delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        return {"message": "用户已删除"}
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    await db.delete(user)
    await db.commit()
    return {"message": "已删除"}


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: uuid.UUID,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = "active"
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/activity-logs", response_model=list[UserActivityLogResponse])
async def list_activity_logs(
    user_id: uuid.UUID | None = None,
    limit: int = Query(200, le=1000),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(UserActivityLog).order_by(UserActivityLog.created_at.desc()).limit(limit)
    if user_id:
        stmt = stmt.where(UserActivityLog.user_id == user_id)
    return (await db.execute(stmt)).scalars().all()


# Personal endpoints (any logged-in user)
me_router = APIRouter(prefix="/me", tags=["我的账户"])


@me_router.get("/activity-logs", response_model=list[UserActivityLogResponse])
async def my_activity_logs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
):
    stmt = (
        select(UserActivityLog)
        .where(UserActivityLog.user_id == user.id)
        .order_by(UserActivityLog.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(stmt)).scalars().all()
