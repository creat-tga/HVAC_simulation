"""Library routers: weather files, equipment models, building templates."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.library import (
    BuildingTemplateCreate,
    BuildingTemplateResponse,
    BuildingTemplateUpdate,
    CloneBuildingToTemplateRequest,
    CloneTemplateToProjectRequest,
    EquipmentModelCreate,
    EquipmentModelResponse,
    EquipmentModelUpdate,
    WeatherFileResponse,
)
from app.schemas.building import BuildingResponse
from app.services import library_service as lib

# ---------- Weather ----------
weather_router = APIRouter(prefix="/weather", tags=["气象数据"])


@weather_router.get("/files", response_model=list[WeatherFileResponse])
async def list_weather(
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await lib.list_weather_files(db, user.id, search)


@weather_router.post("/files", response_model=WeatherFileResponse)
async def upload_weather(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    province: str | None = Form(None),
    city: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".epw"):
        raise HTTPException(status_code=400, detail="仅支持 .epw 文件")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大（>20MB）")
    return await lib.upload_weather_file(db, user.id, file.filename, content, name, province, city)


@weather_router.delete("/files/{file_id}")
async def delete_weather(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await lib.delete_weather_file(db, file_id, user.id, user.role == "admin")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"message": "已删除"}


# ---------- Equipment ----------
equipment_router = APIRouter(prefix="/equipment", tags=["设备模型库"])


@equipment_router.get("", response_model=list[EquipmentModelResponse])
async def list_equipment(
    equipment_type: str | None = None,
    scope: str = Query("all", pattern="^(all|public|mine)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await lib.list_equipment(db, user.id, equipment_type, scope)


@equipment_router.post("", response_model=EquipmentModelResponse)
async def create_equipment(
    data: EquipmentModelCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await lib.create_equipment(db, user.id, user.role == "admin", data.model_dump())


@equipment_router.patch("/{eq_id}", response_model=EquipmentModelResponse)
async def update_equipment(
    eq_id: uuid.UUID,
    data: EquipmentModelUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        eq = await lib.update_equipment(db, eq_id, user.id, user.role == "admin", data.model_dump(exclude_unset=True))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not eq:
        raise HTTPException(status_code=404, detail="设备不存在")
    return eq


@equipment_router.delete("/{eq_id}")
async def delete_equipment(
    eq_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await lib.delete_equipment(db, eq_id, user.id, user.role == "admin")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"message": "已删除"}


# ---------- Building Templates ----------
template_router = APIRouter(prefix="/templates/buildings", tags=["建筑模板库"])


@template_router.get("", response_model=list[BuildingTemplateResponse])
async def list_templates(
    scope: str = Query("all", pattern="^(all|public|mine)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await lib.list_templates(db, user.id, scope)


@template_router.post("", response_model=BuildingTemplateResponse)
async def create_template(
    data: BuildingTemplateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await lib.create_template(db, user.id, user.role == "admin", data.model_dump())


@template_router.patch("/{tpl_id}", response_model=BuildingTemplateResponse)
async def update_template(
    tpl_id: uuid.UUID,
    data: BuildingTemplateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        tpl = await lib.update_template(db, tpl_id, user.id, user.role == "admin", data.model_dump(exclude_unset=True))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return tpl


@template_router.delete("/{tpl_id}")
async def delete_template(
    tpl_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await lib.delete_template(db, tpl_id, user.id, user.role == "admin")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"message": "已删除"}


@template_router.post("/{tpl_id}/clone-to-project", response_model=BuildingResponse)
async def clone_to_project(
    tpl_id: uuid.UUID,
    data: CloneTemplateToProjectRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        bld = await lib.clone_template_to_project(db, tpl_id, data.project_id, data.name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return bld


@template_router.post("/from-building/{building_id}", response_model=BuildingTemplateResponse)
async def clone_from_building(
    building_id: uuid.UUID,
    data: CloneBuildingToTemplateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        tpl = await lib.clone_building_to_template(
            db, building_id, user.id, user.role == "admin",
            data.name, data.description, data.is_public,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return tpl
