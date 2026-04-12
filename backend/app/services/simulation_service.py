import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SyncSession
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
from app.utils.redis_check import is_redis_available

log = logging.getLogger(__name__)

_ep_runner = EnergyPlusRunner()

# ---------------------------------------------------------------------------
# In-process background task tracking (replaces Celery)
# ---------------------------------------------------------------------------
_running_tasks: dict[str, asyncio.Task] = {}

SYSTEM_MODEL_MAP = {
    "efficient_chiller_plant": ChillerSystem,
    "air_cooled_system": AirCooledSystem,
    "free_cooling": FreeCoolingSystem,
    "gshp_system": GSHPSystem,
    # Legacy aliases for backward compatibility with existing DB records
    "chiller": ChillerSystem,
    "air_cooled": AirCooledSystem,
    "gshp": GSHPSystem,
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

async def clear_simulation_results(
    db: AsyncSession, building_id: uuid.UUID, simulation_type: str | None = None,
) -> int:
    """Delete simulation results for a building. Returns number of deleted rows."""
    stmt = delete(SimulationResult).where(SimulationResult.building_id == building_id)
    if simulation_type:
        stmt = stmt.where(SimulationResult.simulation_type == simulation_type)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount  # type: ignore[return-value]


async def get_simulation_results(
    db: AsyncSession, building_id: uuid.UUID
) -> list[SimulationResult]:
    result = await db.execute(
        select(SimulationResult)
        .where(SimulationResult.building_id == building_id)
        .order_by(SimulationResult.created_at.desc())
    )
    return list(result.scalars().all())


async def get_simulation_results_by_type(
    db: AsyncSession, building_id: uuid.UUID, simulation_type: str
) -> list[SimulationResult]:
    result = await db.execute(
        select(SimulationResult)
        .where(
            SimulationResult.building_id == building_id,
            SimulationResult.simulation_type == simulation_type,
        )
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
    """Create a pending SimulationResult and run in-process background task."""
    building = await db.get(Building, building_id)
    if not building:
        raise ValueError("建筑不存在")

    if not building.zones:
        raise ValueError("建筑未配置热区，无法运行仿真")

    if not _ep_runner.is_available():
        raise RuntimeError("EnergyPlus is not installed or not configured")

    sim_result = SimulationResult(
        building_id=building_id,
        simulation_type=data.simulation_type,
        status="pending",
        progress=0,
    )
    db.add(sim_result)
    await db.commit()
    await db.refresh(sim_result)

    result_id = str(sim_result.id)
    task_id = str(uuid.uuid4())
    sim_result.task_id = task_id
    await db.commit()
    await db.refresh(sim_result)

    # Prepare data snapshot for background task (DB session will be closed)
    zones_dict = {z.get("id", str(i)): z for i, z in enumerate(building.zones)}
    location = await _get_building_location(db, building)

    if is_redis_available():
        from app.tasks.simulation_task import run_simulation_task
        run_simulation_task.delay(result_id, str(building_id))
        log.info("Simulation %s dispatched via Celery (task %s)", sim_result.id, task_id)
    else:
        task = asyncio.create_task(
            _run_load_background(result_id, zones_dict, location)
        )
        _running_tasks[result_id] = task
        log.info("Simulation %s dispatched as in-process task (Redis unavailable)", sim_result.id)

    return sim_result


async def create_load_simulation(
    db: AsyncSession, building_id: uuid.UUID
) -> SimulationResult:
    """Create a load simulation and run EnergyPlus in background."""
    building = await db.get(Building, building_id)
    if not building:
        raise ValueError("建筑不存在")

    if not building.zones:
        raise ValueError("建筑未配置分区，无法运行负荷仿真")

    if not _ep_runner.is_available():
        raise RuntimeError("EnergyPlus is not installed or not configured")

    # Clear all previous simulation results before creating new load simulation
    await db.execute(
        delete(SimulationResult).where(SimulationResult.building_id == building_id)
    )

    sim_result = SimulationResult(
        building_id=building_id,
        simulation_type="load",
        status="pending",
        progress=0,
        task_id=str(uuid.uuid4()),
    )
    db.add(sim_result)
    await db.commit()
    await db.refresh(sim_result)

    result_id = str(sim_result.id)

    # Snapshot data for background use (request session will be closed)
    zones_dict = {z.get("id", str(i)): z for i, z in enumerate(building.zones)}
    location = await _get_building_location(db, building)

    if is_redis_available():
        # Dispatch via Celery when Redis is available
        from app.tasks.simulation_task import run_load_simulation_task
        run_load_simulation_task.delay(result_id, str(building_id))
        log.info("Load simulation %s dispatched via Celery", sim_result.id)
    else:
        # Fall back to in-process asyncio task
        task = asyncio.create_task(
            _run_load_background(result_id, zones_dict, location)
        )
        _running_tasks[result_id] = task
        log.info("Load simulation %s dispatched as in-process task (Redis unavailable)", sim_result.id)

    return sim_result


async def create_energy_simulation(
    db: AsyncSession, building_id: uuid.UUID, load_result_id: uuid.UUID
) -> SimulationResult:
    """Create an energy-only simulation that references a completed load result."""
    building = await db.get(Building, building_id)
    if not building:
        raise ValueError("建筑不存在")

    # Validate load result
    load_result = await db.get(SimulationResult, load_result_id)
    if not load_result:
        raise ValueError("负荷仿真结果不存在")
    if load_result.building_id != building_id:
        raise ValueError("负荷仿真结果不属于该建筑")
    if load_result.status != "completed":
        raise ValueError("负荷仿真尚未完成")
    if load_result.simulation_type != "load":
        raise ValueError("指定的仿真结果不是负荷仿真类型")

    # Clear previous energy simulation results
    await db.execute(
        delete(SimulationResult).where(
            SimulationResult.building_id == building_id,
            SimulationResult.simulation_type == "energy",
        )
    )

    sim_result = SimulationResult(
        building_id=building_id,
        simulation_type="energy",
        status="pending",
        progress=0,
        load_result_id=load_result_id,
        task_id=str(uuid.uuid4()),
    )
    db.add(sim_result)
    await db.commit()
    await db.refresh(sim_result)

    result_id = str(sim_result.id)

    # Fetch electricity price from project
    project = await db.get(Project, building.project_id)
    electricity_price = 0.85  # default
    if project and project.electricity_pricing:
        ep = project.electricity_pricing
        electricity_price = ep.get("fixed_price", 0.85)

    # Snapshot data for background
    cooling = load_result.hourly_cooling_load or []
    heating = load_result.hourly_heating_load or []
    hvac_systems = await get_hvac_systems(db, building_id)
    systems_data = [
        {
            "system_type": s.system_type,
            "name": s.name,
            "capacity": s.capacity,
            "cop": s.cop,
            "parameters": s.parameters,
        }
        for s in hvac_systems
    ]

    if is_redis_available():
        from app.tasks.simulation_task import run_energy_simulation_task
        run_energy_simulation_task.delay(result_id, str(building_id), str(load_result_id))
        log.info("Energy simulation %s dispatched via Celery (load ref: %s)", sim_result.id, load_result_id)
    else:
        task = asyncio.create_task(
            _run_energy_background(result_id, cooling, heating, systems_data, electricity_price)
        )
        _running_tasks[result_id] = task
        log.info("Energy simulation %s dispatched as in-process task (load ref: %s)", sim_result.id, load_result_id)

    return sim_result


# ---------------------------------------------------------------------------
# In-process background coroutines (replace Celery tasks)
# ---------------------------------------------------------------------------

def _update_progress_sync(result_id: str, progress: int, message: str = ""):
    """Update simulation progress via sync DB session (safe from worker thread)."""
    with SyncSession() as session:
        result = session.get(SimulationResult, uuid.UUID(result_id))
        if result:
            # Skip update if task already in terminal state (e.g. cancelled)
            if result.status in ("completed", "failed", "cancelled"):
                return
            result.progress = progress
            result.status = "running"
            if result.started_at is None:
                result.started_at = datetime.now(timezone.utc)
            session.commit()


async def _run_load_background(
    result_id: str,
    zones_dict: dict,
    location: list[str],
) -> None:
    """Background coroutine: run EnergyPlus load simulation."""
    try:
        def on_progress(pct: int, msg: str) -> None:
            _update_progress_sync(result_id, pct, msg)

        on_progress(5, "正在启动负荷仿真")

        # Run EnergyPlus in thread pool (sync version with progress)
        cooling, heating = await asyncio.to_thread(
            _ep_runner.run_load_simulation_sync, zones_dict, location, on_progress
        )

        # Save results via sync session
        def save_results() -> None:
            with SyncSession() as session:
                result = session.get(SimulationResult, uuid.UUID(result_id))
                if result and result.status not in ("cancelled", "failed"):
                    result.status = "completed"
                    result.progress = 100
                    result.hourly_cooling_load = cooling
                    result.hourly_heating_load = heating
                    result.total_cooling_load = round(sum(cooling), 2)
                    result.total_heating_load = round(sum(heating), 2)
                    result.peak_cooling_load = round(max(cooling), 2) if cooling else 0.0
                    result.peak_heating_load = round(max(heating), 2) if heating else 0.0
                    result.completed_at = datetime.now(timezone.utc)
                    session.commit()

        await asyncio.to_thread(save_results)
        log.info("Load simulation %s completed successfully", result_id)

    except asyncio.CancelledError:
        def mark_cancelled() -> None:
            with SyncSession() as session:
                result = session.get(SimulationResult, uuid.UUID(result_id))
                if result and result.status not in ("completed", "failed"):
                    result.status = "cancelled"
                    result.error_message = "用户取消"
                    result.completed_at = datetime.now(timezone.utc)
                    session.commit()
        await asyncio.to_thread(mark_cancelled)
        log.info("Load simulation %s was cancelled", result_id)
    except Exception as e:
        log.exception("Load simulation %s failed: %s", result_id, e)

        def mark_failed() -> None:
            with SyncSession() as session:
                result = session.get(SimulationResult, uuid.UUID(result_id))
                if result:
                    result.status = "failed"
                    result.error_message = str(e)[:500]
                    result.completed_at = datetime.now(timezone.utc)
                    session.commit()

        await asyncio.to_thread(mark_failed)
    finally:
        _running_tasks.pop(result_id, None)


async def _run_energy_background(
    result_id: str,
    hourly_cooling: list[float],
    hourly_heating: list[float],
    systems_data: list[dict],
    electricity_price: float = 0.85,
) -> None:
    """Background coroutine: run energy simulation using load results + system models."""
    try:
        _update_progress_sync(result_id, 10, "正在启动能耗仿真")

        def do_energy_calc() -> dict:
            _update_progress_sync(result_id, 30, "正在计算系统能耗")

            sim_input = SimulationInput(
                hourly_cooling_load=hourly_cooling,
                hourly_heating_load=hourly_heating,
                electricity_price=electricity_price,
            )

            total_energy = 0.0
            hourly_energy = [0.0] * 8760
            system_details: list[dict] = []

            for i, sys_info in enumerate(systems_data):
                sys_type = sys_info["system_type"]
                model_cls = SYSTEM_MODEL_MAP.get(sys_type)
                if not model_cls:
                    log.warning("Unknown system type: %s, skipping", sys_type)
                    continue

                spec = SystemSpec(
                    name=sys_info.get("name", f"System-{i+1}"),
                    capacity=sys_info.get("capacity") or 100.0,
                    cop=sys_info.get("cop") or 4.0,
                    parameters=sys_info.get("parameters") or {},
                )
                model = model_cls(spec)
                result = model.simulate(sim_input)

                for h in range(min(len(result.hourly_energy), 8760)):
                    hourly_energy[h] += result.hourly_energy[h]
                total_energy += result.total_energy

                system_details.append({
                    "name": sys_info["name"],
                    "system_type": sys_type,
                    "total_energy": result.total_energy,
                })

                pct = 30 + int(60 * (i + 1) / len(systems_data))
                _update_progress_sync(result_id, pct, f"已完成 {sys_info['name']} 计算")

            return {
                "hourly_energy": hourly_energy,
                "total_energy": round(total_energy, 2),
                "system_details": system_details,
            }

        calc = await asyncio.to_thread(do_energy_calc)

        def save_energy_results() -> None:
            with SyncSession() as session:
                result = session.get(SimulationResult, uuid.UUID(result_id))
                if result and result.status not in ("cancelled", "failed"):
                    result.status = "completed"
                    result.progress = 100
                    result.hourly_energy = calc["hourly_energy"]
                    result.total_energy = calc["total_energy"]
                    result.result_data = {"system_details": calc["system_details"]}
                    result.completed_at = datetime.now(timezone.utc)
                    session.commit()

        await asyncio.to_thread(save_energy_results)
        log.info("Energy simulation %s completed successfully", result_id)

    except asyncio.CancelledError:
        def mark_cancelled() -> None:
            with SyncSession() as session:
                result = session.get(SimulationResult, uuid.UUID(result_id))
                if result and result.status not in ("completed", "failed"):
                    result.status = "cancelled"
                    result.error_message = "用户取消"
                    result.completed_at = datetime.now(timezone.utc)
                    session.commit()
        await asyncio.to_thread(mark_cancelled)
    except Exception as e:
        log.exception("Energy simulation %s failed: %s", result_id, e)

        def mark_failed() -> None:
            with SyncSession() as session:
                result = session.get(SimulationResult, uuid.UUID(result_id))
                if result:
                    result.status = "failed"
                    result.error_message = str(e)[:500]
                    result.completed_at = datetime.now(timezone.utc)
                    session.commit()

        await asyncio.to_thread(mark_failed)
    finally:
        _running_tasks.pop(result_id, None)


# ---------------------------------------------------------------------------
# Status & cancellation (no Celery dependency)
# ---------------------------------------------------------------------------

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

    rid = str(result_id)

    # Try cancel Celery task first (if dispatched via Celery)
    if result.task_id and is_redis_available():
        try:
            from app.celery_app import celery_app
            if celery_app is not None:
                celery_app.control.revoke(result.task_id, terminate=True)
                log.info("Revoked Celery task %s for simulation %s", result.task_id, result_id)
        except Exception:
            log.warning("Failed to revoke Celery task %s", result.task_id, exc_info=True)

    # Cancel in-process asyncio task (if running in-process)
    task = _running_tasks.get(rid)
    if task and not task.done():
        task.cancel()
        log.info("Cancelled in-process task for simulation %s", result_id)

    result.status = "cancelled"
    result.error_message = "用户取消"
    result.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(result)
    return result
