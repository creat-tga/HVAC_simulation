"""System scheme API routes (项目级 + 子系统层级)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.library import EquipmentModelResponse
from app.schemas.system_scheme import (
    CapacitySummary,
    SystemSchemeCreate,
    SystemSchemeListItem,
    SystemSchemeResponse,
    SystemSchemeUpdate,
    ValidationReport,
)
from app.services import library_service as lib
from app.services import system_scheme_service as svc

router = APIRouter(prefix="/projects/{project_id}/system-schemes", tags=["系统方案"])
scheme_router = APIRouter(prefix="/system-schemes", tags=["系统方案-单方案"])


async def _check_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    p = await db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p


# -------------------- project-level --------------------

@router.get("", response_model=list[SystemSchemeListItem])
async def list_schemes(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _check_project(db, project_id)
    return await svc.list_scheme_items(db, project_id)


@router.post("", response_model=SystemSchemeResponse, status_code=201)
async def create_scheme(
    project_id: uuid.UUID,
    data: SystemSchemeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _check_project(db, project_id)
    if not data.control_strategy:
        data.control_strategy = svc.default_control_strategy()
    try:
        return await svc.create_scheme(db, project_id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/validate", response_model=ValidationReport)
async def validate_all(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _check_project(db, project_id)
    return await svc.validate_project_schemes(db, project_id)


# -------------------- single scheme --------------------

@scheme_router.get("/{scheme_id}", response_model=SystemSchemeResponse)
async def get_scheme(
    scheme_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = await svc.get_scheme(db, scheme_id)
    if not s:
        raise HTTPException(404, "方案不存在")
    return s


@scheme_router.get("/{scheme_id}/derived")
async def get_scheme_derived(
    scheme_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    s = await svc.get_scheme(db, scheme_id)
    if not s:
        raise HTTPException(404, "方案不存在")
    return await svc.compute_scheme_derived(db, s)


@scheme_router.get("/{scheme_id}/summary", response_model=CapacitySummary)
async def get_summary(
    scheme_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = await svc.get_scheme(db, scheme_id)
    if not s:
        raise HTTPException(404, "方案不存在")
    return await svc.get_scheme_summary(db, s)


@scheme_router.post("/{scheme_id}/validate", response_model=ValidationReport)
async def validate_scheme(
    scheme_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await svc.validate_single_scheme(db, scheme_id)


@scheme_router.post("/{scheme_id}/validate-payload", response_model=ValidationReport)
async def validate_scheme_payload(
    scheme_id: uuid.UUID,
    data: SystemSchemeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dry-run validation against an unsaved payload (no DB writes)."""
    return await svc.validate_scheme_payload(db, scheme_id, data)


@scheme_router.put("/{scheme_id}", response_model=SystemSchemeResponse)
async def update_scheme(
    scheme_id: uuid.UUID,
    data: SystemSchemeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = await svc.get_scheme(db, scheme_id)
    if not s:
        raise HTTPException(404, "方案不存在")
    try:
        return await svc.update_scheme(db, scheme_id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@scheme_router.delete("/{scheme_id}")
async def delete_scheme(
    scheme_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = await svc.delete_scheme(db, scheme_id)
    if not ok:
        raise HTTPException(404, "方案不存在")
    return {"message": "已删除"}


# -------------------- equipment search --------------------

eq_search_router = APIRouter(prefix="/equipment-search", tags=["设备查询"])


@eq_search_router.get("", response_model=list[EquipmentModelResponse])
async def search_equipment(
    equipment_type: str = Query(...),
    name: str | None = Query(None),
    capacity_min: float | None = None,
    capacity_max: float | None = None,
    flow_min: float | None = None,
    flow_max: float | None = None,
    head_min: float | None = None,
    head_max: float | None = None,
    efficiency_min: float | None = None,
    efficiency_max: float | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await lib.search_equipment_records(
        db,
        user.id,
        equipment_type,
        name=name,
        capacity_min=capacity_min,
        capacity_max=capacity_max,
        flow_min=flow_min,
        flow_max=flow_max,
        head_min=head_min,
        head_max=head_max,
        efficiency_min=efficiency_min,
        efficiency_max=efficiency_max,
    )
