import logging
import uuid

from celery.result import AsyncResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.models.building import Building
from app.models.project import Project
from app.models.simulation import HVACSystem, SimulationResult
from app.schemas.simulation import HVACSystemCreate, HVACSystemUpdate, SimulationCreate
from app.simulation.energyplus.runner import EnergyPlusRunner
from app.simulation.systems.base import SystemSpec, SimulationInput
from app.simulation.systems.chiller import ChillerSystem
from app.simulation.systems.air_cooled import AirCooledSystem
from app.simulation.systems.free_cooling import FreeCoolingSystem
from app.simulation.systems.gshp import GSHPSystem

log = logging.getLogger(__name__)

_ep_runner = EnergyPlusRunner()

SYSTEM_MODEL_MAP = {
    "efficient_chiller_plant": ChillerSystem,
    "chiller": ChillerSystem,
    "air_cooled": AirCooledSystem,
    "air_cooled_system": AirCooledSystem,
    "free_cooling": FreeCoolingSystem,
    "gshp": GSHPSystem,
    "gshp_system": GSHPSystem,
}


# HVAC System CRUD
async def get_hvac_systems(
    db: AsyncSession, building_id: uuid.UUID
) -> list[HVACSystem]:
    result = await db.execute(
        select(HVACSystem).where(HVACSystem.building_id == building_id)
    )
    return list(result.scalars().all())


async def create_hvac_system(
    db: AsyncSession, building_id: uuid.UUID, data: HVACSystemCreate
) -> HVACSystem:
    system = HVACSystem(building_id=building_id, **data.model_dump())
    db.add(system)
    await db.commit()
    await db.refresh(system)
    return system


async def update_hvac_system(
    db: AsyncSession, system_id: uuid.UUID, data: HVACSystemUpdate
) -> HVACSystem | None:
    system = await db.get(HVACSystem, system_id)
    if not system:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(system, key, value)
    await db.commit()
    await db.refresh(system)
    return system


async def delete_hvac_system(db: AsyncSession, system_id: uuid.UUID) -> bool:
    system = await db.get(HVACSystem, system_id)
    if not system:
        return False
    await db.delete(system)
    await db.commit()
    return True


async def _generate_loads(
    location: list[str],
    zones: list[dict] | None,
) -> tuple[list[float], list[float]]:
    """Generate hourly loads via EnergyPlus; returns (cooling, heating)."""
    if not _ep_runner.is_available():
        raise RuntimeError("EnergyPlus is not installed or not configured")
    if not zones:
        raise ValueError("Building zones are required for EnergyPlus simulation")

    zones_dict = {z.get("id", str(i)): z for i, z in enumerate(zones)}
    log.info("Running EnergyPlus load simulation (%d zones, %s)", len(zones), location)
    cooling, heating = await _ep_runner.run_load_simulation(
        zones_dict, location
    )
    log.info("EnergyPlus completed successfully")
    return cooling, heating


def _parse_location(loc_str: str | None) -> list[str]:
    """Parse location string (e.g. "广东-广州") into [province, city]."""
    if not loc_str:
        return ["上海", "上海"]
    parts = loc_str.split("-")
    if len(parts) >= 2:
        return parts[:2]
    return [parts[0], parts[0]]


async def _get_building_location(db: AsyncSession, building: Building) -> list[str]:
    """Get location list for a building, preferring project's location."""
    project = await db.get(Project, building.project_id)
    project_loc = project.location if project else None
    return _parse_location(project_loc or building.location)


# Load Preview (calculate only, no save)
async def preview_building_load(
    db: AsyncSession, building_id: uuid.UUID
) -> dict | None:
    """Generate hourly loads for a building without saving to DB."""
    building = await db.get(Building, building_id)
    if not building:
        return None

    zones = building.zones
    location = await _get_building_location(db, building)

    hourly_cooling, hourly_heating = await _generate_loads(location, zones)

    return {
        "hourly_cooling_load": hourly_cooling,
        "hourly_heating_load": hourly_heating,
        "total_cooling_load": round(sum(hourly_cooling), 2),
        "total_heating_load": round(sum(hourly_heating), 2),
        "peak_cooling_load": round(max(hourly_cooling), 2) if hourly_cooling else 0.0,
        "peak_heating_load": round(max(hourly_heating), 2) if hourly_heating else 0.0,
    }


# Simulation
async def get_simulation_results(
    db: AsyncSession, building_id: uuid.UUID
) -> list[SimulationResult]:
    result = await db.execute(
        select(SimulationResult)
        .where(SimulationResult.building_id == building_id)
        .order_by(SimulationResult.created_at.desc())
    )
    return list(result.scalars().all())


async def get_simulation_result(
    db: AsyncSession, result_id: uuid.UUID
) -> SimulationResult | None:
    return await db.get(SimulationResult, result_id)


async def create_simulation(
    db: AsyncSession, building_id: uuid.UUID, data: SimulationCreate
) -> SimulationResult:
    """Create a pending SimulationResult and dispatch a Celery background task."""
    building = await db.get(Building, building_id)
    if not building:
        raise ValueError("建筑不存在")

    if not building.zones:
        raise ValueError("建筑未配置热区，无法运行仿真")

    if not _ep_runner.is_available():
        raise RuntimeError("EnergyPlus is not installed or not configured")

    # Create pending record
    sim_result = SimulationResult(
        building_id=building_id,
        simulation_type=data.simulation_type,
        status="pending",
        progress=0,
    )
    db.add(sim_result)
    await db.commit()
    await db.refresh(sim_result)

    # Dispatch Celery task
    from app.tasks.simulation_task import run_simulation_task

    task = run_simulation_task.delay(str(sim_result.id), str(building_id))

    # Store the Celery task ID
    sim_result.task_id = task.id
    await db.commit()
    await db.refresh(sim_result)

    log.info(
        "Simulation %s dispatched as Celery task %s", sim_result.id, task.id
    )
    return sim_result


async def get_simulation_status(
    db: AsyncSession, result_id: uuid.UUID
) -> SimulationResult | None:
    """Get current simulation status (lightweight, for polling)."""
    return await db.get(SimulationResult, result_id)


async def cancel_simulation(
    db: AsyncSession, result_id: uuid.UUID
) -> SimulationResult | None:
    """Cancel a running or pending simulation."""
    result = await db.get(SimulationResult, result_id)
    if not result:
        return None

    if result.status in ("completed", "failed", "cancelled"):
        return result  # Already terminal

    # Revoke Celery task
    if result.task_id:
        celery_app.control.revoke(result.task_id, terminate=True, signal="SIGTERM")
        log.info("Revoked Celery task %s for simulation %s", result.task_id, result_id)

    result.status = "cancelled"
    result.error_message = "用户取消"
    from datetime import datetime, timezone
    result.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(result)
    return result
