import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.building import Building
from app.schemas.simulation import (
    HVACSystemCreate,
    HVACSystemUpdate,
    HVACSystemResponse,
    SimulationCreate,
    SimulationResponse,
    SimulationDetailResponse,
    SimulationStatusResponse,
)
from app.services import simulation_service

router = APIRouter(prefix="/buildings/{building_id}", tags=["仿真管理"])


# --- Weather Data ---
@router.get("/weather-data")
async def get_weather_data(
    building_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取建筑对应位置的逐时气象数据（干球温度、露点温度、相对湿度）"""
    from app.simulation.energyplus.weather_utils import find_epw_for_location, parse_epw_hourly

    building = await db.get(Building, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="建筑不存在")

    # Get location: project.location first, fallback to building.location
    from app.models.project import Project
    project = await db.get(Project, building.project_id)
    loc_str = (project.location if project else None) or building.location

    location_parts: list[str] = []
    if loc_str:
        location_parts = [p.strip() for p in loc_str.split("-") if p.strip()]

    if not location_parts:
        raise HTTPException(status_code=400, detail="项目未设置地点信息，请在项目设置中配置地点")

    epw_path, _header = find_epw_for_location(location_parts)
    if not epw_path:
        raise HTTPException(status_code=404, detail="未找到对应的气象数据文件")

    import asyncio
    data = await asyncio.to_thread(parse_epw_hourly, epw_path)
    return JSONResponse(content=data)


# --- Load Simulation (background task) ---
@router.post("/load-simulation", response_model=SimulationResponse, status_code=201)
async def run_load_simulation(
    building_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """提交负荷仿真任务（后台运行 EnergyPlus）"""
    try:
        return await simulation_service.create_load_simulation(db, building_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# --- Energy Simulation (uses existing load results) ---
@router.post("/energy-simulation", response_model=SimulationResponse, status_code=201)
async def run_energy_simulation(
    building_id: uuid.UUID,
    data: SimulationCreate,
    db: AsyncSession = Depends(get_db),
):
    """提交能耗仿真任务（基于已完成的负荷仿真结果）"""
    if not data.load_result_id:
        raise HTTPException(status_code=400, detail="必须指定负荷仿真结果ID (load_result_id)")
    try:
        return await simulation_service.create_energy_simulation(
            db, building_id, data.load_result_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    building_id: uuid.UUID,
    simulation_type: str | None = Query(None, description="Filter by type: load, energy, full_year"),
    db: AsyncSession = Depends(get_db),
):
    """获取建筑的仿真结果列表（可按类型筛选）"""
    if simulation_type:
        return await simulation_service.get_simulation_results_by_type(
            db, building_id, simulation_type
        )
    return await simulation_service.get_simulation_results(db, building_id)


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


@router.get(
    "/simulations/{result_id}/status", response_model=SimulationStatusResponse
)
async def get_simulation_status(
    building_id: uuid.UUID,
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """查询仿真任务状态与进度"""
    result = await simulation_service.get_simulation_status(db, result_id)
    if not result or result.building_id != building_id:
        raise HTTPException(status_code=404, detail="仿真结果不存在")
    return result


@router.post(
    "/simulations/{result_id}/cancel", response_model=SimulationStatusResponse
)
async def cancel_simulation(
    building_id: uuid.UUID,
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """取消正在运行或等待中的仿真任务"""
    result = await simulation_service.cancel_simulation(db, result_id)
    if not result or result.building_id != building_id:
        raise HTTPException(status_code=404, detail="仿真结果不存在")
    return result


