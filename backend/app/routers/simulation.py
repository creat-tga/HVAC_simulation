import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.simulation import (
    HVACSystemCreate,
    HVACSystemUpdate,
    HVACSystemResponse,
    SimulationCreate,
    SimulationResponse,
    SimulationDetailResponse,
)
from app.services import simulation_service

router = APIRouter(prefix="/buildings/{building_id}", tags=["仿真管理"])


# --- HVAC Systems ---
@router.get("/systems", response_model=list[HVACSystemResponse])
async def list_hvac_systems(
    building_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取建筑下所有HVAC系统"""
    return await simulation_service.get_hvac_systems(db, building_id)


@router.post("/systems", response_model=HVACSystemResponse, status_code=201)
async def create_hvac_system(
    building_id: uuid.UUID,
    data: HVACSystemCreate,
    db: AsyncSession = Depends(get_db),
):
    """添加HVAC系统"""
    return await simulation_service.create_hvac_system(db, building_id, data)


@router.put("/systems/{system_id}", response_model=HVACSystemResponse)
async def update_hvac_system(
    building_id: uuid.UUID,
    system_id: uuid.UUID,
    data: HVACSystemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新HVAC系统"""
    system = await simulation_service.update_hvac_system(db, system_id, data)
    if not system:
        raise HTTPException(status_code=404, detail="系统不存在")
    return system


@router.delete("/systems/{system_id}", status_code=204)
async def delete_hvac_system(
    building_id: uuid.UUID,
    system_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """删除HVAC系统"""
    if not await simulation_service.delete_hvac_system(db, system_id):
        raise HTTPException(status_code=404, detail="系统不存在")


# --- Simulations ---
@router.get("/simulations", response_model=list[SimulationResponse])
async def list_simulations(
    building_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取建筑的仿真结果列表"""
    return await simulation_service.get_simulation_results(db, building_id)


@router.post("/simulations", response_model=SimulationResponse, status_code=201)
async def run_simulation(
    building_id: uuid.UUID,
    data: SimulationCreate,
    db: AsyncSession = Depends(get_db),
):
    """启动仿真任务"""
    return await simulation_service.create_simulation(db, building_id, data)


@router.get("/simulations/{result_id}", response_model=SimulationDetailResponse)
async def get_simulation_detail(
    building_id: uuid.UUID,
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取仿真结果详情"""
    result = await simulation_service.get_simulation_result(db, result_id)
    if not result or result.building_id != building_id:
        raise HTTPException(status_code=404, detail="仿真结果不存在")
    return result
