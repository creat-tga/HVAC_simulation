import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.building import BuildingCreate, BuildingUpdate, BuildingResponse
from app.services import building_service
from app.services.building_service import BuildingLimitError

router = APIRouter(prefix="/projects/{project_id}/buildings", tags=["建筑管理"])


@router.get("/", response_model=list[BuildingResponse])
async def list_buildings(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取项目下所有建筑"""
    return await building_service.get_buildings(db, project_id)


@router.get("/{building_id}", response_model=BuildingResponse)
async def get_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取建筑详情"""
    building = await building_service.get_building(db, building_id)
    if not building or building.project_id != project_id:
        raise HTTPException(status_code=404, detail="建筑不存在")
    return building


@router.post("/", response_model=BuildingResponse, status_code=201)
async def create_building(
    project_id: uuid.UUID,
    data: BuildingCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建新建筑"""
    try:
        return await building_service.create_building(db, project_id, data)
    except BuildingLimitError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{building_id}", response_model=BuildingResponse)
async def update_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    data: BuildingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新建筑信息"""
    building = await building_service.update_building(db, building_id, data)
    if not building or building.project_id != project_id:
        raise HTTPException(status_code=404, detail="建筑不存在")
    return building


@router.delete("/{building_id}", status_code=204)
async def delete_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """删除建筑"""
    building = await building_service.get_building(db, building_id)
    if not building or building.project_id != project_id:
        raise HTTPException(status_code=404, detail="建筑不存在")
    await building_service.delete_building(db, building_id)
