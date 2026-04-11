"""Celery tasks: load simulation (EnergyPlus) and energy simulation (system models)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import redis

from app.celery_app import celery_app
from app.config import settings
from app.database import SyncSession
from app.models.building import Building
from app.models.project import Project
from app.models.simulation import HVACSystem, SimulationResult
from app.simulation.energyplus.runner import EnergyPlusRunner
from app.simulation.systems.base import SystemSpec, SimulationInput
from app.simulation.systems.chiller import ChillerSystem
from app.simulation.systems.air_cooled import AirCooledSystem
from app.simulation.systems.free_cooling import FreeCoolingSystem
from app.simulation.systems.gshp import GSHPSystem

log = logging.getLogger(__name__)

SYSTEM_MODEL_MAP = {
    "efficient_chiller_plant": ChillerSystem,
    "chiller": ChillerSystem,
    "air_cooled": AirCooledSystem,
    "air_cooled_system": AirCooledSystem,
    "free_cooling": FreeCoolingSystem,
    "gshp": GSHPSystem,
    "gshp_system": GSHPSystem,
}

_ep_runner = EnergyPlusRunner()


def _get_redis() -> redis.Redis | None:
    """Get Redis client, or None if Redis is not available."""
    try:
        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def _publish_progress(
    r: redis.Redis | None,
    result_id: str,
    progress: int,
    status: str,
    message: str = "",
) -> None:
    if r is None:
        return
    try:
        payload = json.dumps({
            "id": result_id,
            "progress": progress,
            "status": status,
            "message": message,
        })
        r.publish(f"simulation:{result_id}", payload)
    except Exception:
        pass  # Redis publish failure is non-fatal


def _update_db_progress(result_id: str, progress: int, status: str = "running") -> None:
    with SyncSession() as db:
        result = db.get(SimulationResult, uuid.UUID(result_id))
        if result:
            result.progress = progress
            result.status = status
            db.commit()


def _parse_location(loc_str: str | None) -> list[str]:
    if not loc_str:
        return ["上海", "上海"]
    parts = loc_str.split("-")
    if len(parts) >= 2:
        return parts[:2]
    return [parts[0], parts[0]]


def _mark_failed(result_id: str, exc: Exception, r: redis.Redis | None) -> None:
    with SyncSession() as db:
        result = db.get(SimulationResult, uuid.UUID(result_id))
        if result:
            result.status = "failed"
            result.error_message = str(exc)[:2000]
            result.completed_at = datetime.now(timezone.utc)
            db.commit()
            _publish_progress(r, result_id, result.progress, "failed", str(exc)[:500])


# ---------------------------------------------------------------------------
#  Load Simulation Task (EnergyPlus only)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
    name="app.tasks.simulation_task.run_load_simulation_task",
)
def run_load_simulation_task(self, simulation_result_id: str, building_id: str) -> dict:
    """Run EnergyPlus load simulation only. Saves hourly loads to DB."""
    r = _get_redis()

    def on_ep_progress(percent: int, message: str) -> None:
        # EnergyPlus progress mapped to 10-90 range
        mapped = 10 + int(percent * 0.8)
        _update_db_progress(simulation_result_id, mapped)
        _publish_progress(r, simulation_result_id, mapped, "running", message)

    try:
        # Mark running
        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if not result:
                raise ValueError(f"SimulationResult {simulation_result_id} not found")
            result.status = "running"
            result.task_id = self.request.id
            result.progress = 5
            result.started_at = datetime.now(timezone.utc)
            db.commit()

        _publish_progress(r, simulation_result_id, 5, "running", "负荷仿真任务开始")

        # Load building data
        with SyncSession() as db:
            building = db.get(Building, uuid.UUID(building_id))
            if not building:
                raise ValueError(f"Building {building_id} not found")
            zones = building.zones
            project = db.get(Project, building.project_id)
            project_loc = project.location if project else None
            location = _parse_location(project_loc or building.location)

        if not zones:
            raise ValueError("建筑未配置分区，无法运行负荷仿真")

        zones_dict = {z.get("id", str(i)): z for i, z in enumerate(zones)}

        _update_db_progress(simulation_result_id, 10)
        _publish_progress(r, simulation_result_id, 10, "running", "建筑数据加载完成，开始 EnergyPlus 仿真")

        # Run EnergyPlus
        hourly_cooling, hourly_heating = _ep_runner.run_load_simulation_sync(
            zones_dict, location, on_progress=on_ep_progress
        )

        total_cooling = round(sum(hourly_cooling), 2)
        total_heating = round(sum(hourly_heating), 2)
        peak_cooling = round(max(hourly_cooling), 2) if hourly_cooling else 0.0
        peak_heating = round(max(hourly_heating), 2) if hourly_heating else 0.0

        _update_db_progress(simulation_result_id, 95)
        _publish_progress(r, simulation_result_id, 95, "running", "正在保存负荷结果")

        # Save load results
        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if not result:
                raise ValueError("SimulationResult disappeared during task execution")
            result.status = "completed"
            result.progress = 100
            result.completed_at = datetime.now(timezone.utc)
            result.hourly_cooling_load = hourly_cooling
            result.hourly_heating_load = hourly_heating
            result.total_cooling_load = total_cooling
            result.total_heating_load = total_heating
            result.peak_cooling_load = peak_cooling
            result.peak_heating_load = peak_heating
            db.commit()

        _publish_progress(r, simulation_result_id, 100, "completed", "负荷仿真完成")
        log.info("Load simulation %s completed", simulation_result_id)
        return {"status": "completed", "simulation_result_id": simulation_result_id}

    except Exception as exc:
        log.exception("Load simulation task %s failed: %s", simulation_result_id, exc)
        _mark_failed(simulation_result_id, exc, r)

        if self.request.retries < self.max_retries:
            with SyncSession() as db:
                result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
                if result:
                    result.status = "pending"
                    result.error_message = f"重试中 ({self.request.retries + 1}/{self.max_retries}): {str(exc)[:500]}"
                    db.commit()
            raise self.retry(exc=exc)
        raise


# ---------------------------------------------------------------------------
#  Energy Simulation Task (system models, uses existing load results)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
    name="app.tasks.simulation_task.run_energy_simulation_task",
)
def run_energy_simulation_task(
    self,
    simulation_result_id: str,
    building_id: str,
    load_result_id: str,
) -> dict:
    """Run energy simulation using existing load results + HVAC system models."""
    r = _get_redis()

    try:
        # Mark running
        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if not result:
                raise ValueError(f"SimulationResult {simulation_result_id} not found")
            result.status = "running"
            result.task_id = self.request.id
            result.progress = 5
            result.started_at = datetime.now(timezone.utc)
            db.commit()

        _publish_progress(r, simulation_result_id, 5, "running", "能耗仿真任务开始")

        # Load the load simulation results
        with SyncSession() as db:
            load_result = db.get(SimulationResult, uuid.UUID(load_result_id))
            if not load_result:
                raise ValueError("负荷仿真结果不存在")
            if load_result.status != "completed":
                raise ValueError("负荷仿真尚未完成")
            hourly_cooling = load_result.hourly_cooling_load
            hourly_heating = load_result.hourly_heating_load
            peak_cooling = load_result.peak_cooling_load or 0.0
            peak_heating = load_result.peak_heating_load or 0.0
            total_cooling = load_result.total_cooling_load or 0.0
            total_heating = load_result.total_heating_load or 0.0

        if not hourly_cooling or not hourly_heating:
            raise ValueError("负荷仿真结果中没有逐时负荷数据")

        _update_db_progress(simulation_result_id, 20)
        _publish_progress(r, simulation_result_id, 20, "running", "负荷数据加载完成，开始计算系统能耗")

        # Load HVAC systems
        with SyncSession() as db:
            hvac_systems = (
                db.query(HVACSystem)
                .filter(HVACSystem.building_id == uuid.UUID(building_id))
                .all()
            )

        electricity_price = 0.85
        hourly_energy = [0.0] * 8760
        total_energy = 0.0
        total_cost = 0.0
        total_carbon = 0.0
        monthly_cost = [0.0] * 12
        monthly_carbon = [0.0] * 12
        monthly_energy = [0.0] * 12

        _update_db_progress(simulation_result_id, 40)
        _publish_progress(r, simulation_result_id, 40, "running", "计算系统能耗中")

        if hvac_systems:
            for hvac in hvac_systems:
                model_cls = SYSTEM_MODEL_MAP.get(hvac.system_type, ChillerSystem)
                spec = SystemSpec(
                    name=hvac.name,
                    capacity=hvac.capacity or peak_cooling,
                    cop=hvac.cop or 5.0,
                    parameters=hvac.parameters or {},
                )
                model = model_cls(spec)
                sim_input = SimulationInput(
                    hourly_cooling_load=hourly_cooling,
                    hourly_heating_load=hourly_heating,
                    electricity_price=electricity_price,
                )
                output = model.simulate(sim_input)
                for i in range(8760):
                    hourly_energy[i] += output.hourly_energy[i]
                total_energy += output.total_energy
                total_cost += output.total_cost
                total_carbon += output.total_carbon
                for m in range(12):
                    monthly_cost[m] += output.monthly_cost[m]
                    monthly_carbon[m] += output.monthly_carbon[m]
                    monthly_energy[m] += output.monthly_energy[m]
        else:
            default_cop = 5.0
            for i in range(8760):
                e = hourly_cooling[i] / default_cop if hourly_cooling[i] > 0 else 0.0
                hourly_energy[i] = round(e, 2)
            total_energy = round(sum(hourly_energy), 2)
            total_cost = round(total_energy * electricity_price, 2)
            total_carbon = round(total_energy * 0.581, 2)

            days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            offset = 0
            for m, days in enumerate(days_per_month):
                hours = days * 24
                monthly_energy[m] = round(sum(hourly_energy[offset : offset + hours]), 2)
                monthly_cost[m] = round(monthly_energy[m] * electricity_price, 2)
                monthly_carbon[m] = round(monthly_energy[m] * 0.581, 2)
                offset += hours

        hourly_energy = [round(e, 2) for e in hourly_energy]

        _update_db_progress(simulation_result_id, 90)
        _publish_progress(r, simulation_result_id, 90, "running", "正在保存能耗结果")

        # Save results
        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if not result:
                raise ValueError("SimulationResult disappeared during task execution")
            result.status = "completed"
            result.progress = 100
            result.completed_at = datetime.now(timezone.utc)
            # Copy load data for self-contained reporting
            result.hourly_cooling_load = hourly_cooling
            result.hourly_heating_load = hourly_heating
            result.total_cooling_load = total_cooling
            result.total_heating_load = total_heating
            result.peak_cooling_load = peak_cooling
            result.peak_heating_load = peak_heating
            # Energy results
            result.hourly_energy = hourly_energy
            result.total_energy = round(total_energy, 2)
            result.total_cost = round(total_cost, 2)
            result.total_carbon = round(total_carbon, 2)
            result.result_data = {
                "electricity_cost": round(total_cost, 2),
                "monthly_cost": [round(c, 2) for c in monthly_cost],
                "monthly_carbon": [round(c, 2) for c in monthly_carbon],
                "monthly_energy": [round(e, 2) for e in monthly_energy],
                "carbon_factor": 0.581,
            }
            db.commit()

        _publish_progress(r, simulation_result_id, 100, "completed", "能耗仿真完成")
        log.info("Energy simulation %s completed", simulation_result_id)
        return {"status": "completed", "simulation_result_id": simulation_result_id}

    except Exception as exc:
        log.exception("Energy simulation task %s failed: %s", simulation_result_id, exc)
        _mark_failed(simulation_result_id, exc, r)

        if self.request.retries < self.max_retries:
            with SyncSession() as db:
                result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
                if result:
                    result.status = "pending"
                    result.error_message = f"重试中 ({self.request.retries + 1}/{self.max_retries}): {str(exc)[:500]}"
                    db.commit()
            raise self.retry(exc=exc)
        raise


# ---------------------------------------------------------------------------
#  Legacy: Full simulation task (kept for backward compatibility)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
    name="app.tasks.simulation_task.run_simulation_task",
)
def run_simulation_task(self, simulation_result_id: str, building_id: str) -> dict:
    """Run full EnergyPlus simulation + system energy calculation (legacy combined task)."""
    r = _get_redis()

    def on_ep_progress(percent: int, message: str) -> None:
        _update_db_progress(simulation_result_id, percent)
        _publish_progress(r, simulation_result_id, percent, "running", message)

    try:
        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if not result:
                raise ValueError(f"SimulationResult {simulation_result_id} not found")
            result.status = "running"
            result.task_id = self.request.id
            result.progress = 5
            result.started_at = datetime.now(timezone.utc)
            db.commit()

        _publish_progress(r, simulation_result_id, 5, "running", "任务开始")

        with SyncSession() as db:
            building = db.get(Building, uuid.UUID(building_id))
            if not building:
                raise ValueError(f"Building {building_id} not found")
            zones = building.zones
            project = db.get(Project, building.project_id)
            project_loc = project.location if project else None
            location = _parse_location(project_loc or building.location)

        if not zones:
            raise ValueError("Building zones are required for EnergyPlus simulation")

        zones_dict = {z.get("id", str(i)): z for i, z in enumerate(zones)}

        _update_db_progress(simulation_result_id, 10)
        _publish_progress(r, simulation_result_id, 10, "running", "建筑数据加载完成")

        hourly_cooling, hourly_heating = _ep_runner.run_load_simulation_sync(
            zones_dict, location, on_progress=on_ep_progress
        )

        total_cooling = round(sum(hourly_cooling), 2)
        total_heating = round(sum(hourly_heating), 2)
        peak_cooling = round(max(hourly_cooling), 2) if hourly_cooling else 0.0
        peak_heating = round(max(hourly_heating), 2) if hourly_heating else 0.0

        _update_db_progress(simulation_result_id, 75)
        _publish_progress(r, simulation_result_id, 75, "running", "开始计算系统能耗")

        with SyncSession() as db:
            hvac_systems = (
                db.query(HVACSystem)
                .filter(HVACSystem.building_id == uuid.UUID(building_id))
                .all()
            )

        electricity_price = 0.85
        hourly_energy = [0.0] * 8760
        total_energy = 0.0
        total_cost = 0.0
        total_carbon = 0.0
        monthly_cost = [0.0] * 12
        monthly_carbon = [0.0] * 12
        monthly_energy = [0.0] * 12

        if hvac_systems:
            for hvac in hvac_systems:
                model_cls = SYSTEM_MODEL_MAP.get(hvac.system_type, ChillerSystem)
                spec = SystemSpec(
                    name=hvac.name,
                    capacity=hvac.capacity or peak_cooling,
                    cop=hvac.cop or 5.0,
                    parameters=hvac.parameters or {},
                )
                model = model_cls(spec)
                sim_input = SimulationInput(
                    hourly_cooling_load=hourly_cooling,
                    hourly_heating_load=hourly_heating,
                    electricity_price=electricity_price,
                )
                output = model.simulate(sim_input)
                for i in range(8760):
                    hourly_energy[i] += output.hourly_energy[i]
                total_energy += output.total_energy
                total_cost += output.total_cost
                total_carbon += output.total_carbon
                for m in range(12):
                    monthly_cost[m] += output.monthly_cost[m]
                    monthly_carbon[m] += output.monthly_carbon[m]
                    monthly_energy[m] += output.monthly_energy[m]
        else:
            default_cop = 5.0
            for i in range(8760):
                e = hourly_cooling[i] / default_cop if hourly_cooling[i] > 0 else 0.0
                hourly_energy[i] = round(e, 2)
            total_energy = round(sum(hourly_energy), 2)
            total_cost = round(total_energy * electricity_price, 2)
            total_carbon = round(total_energy * 0.581, 2)

            days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            offset = 0
            for m, days in enumerate(days_per_month):
                hours = days * 24
                monthly_energy[m] = round(sum(hourly_energy[offset : offset + hours]), 2)
                monthly_cost[m] = round(monthly_energy[m] * electricity_price, 2)
                monthly_carbon[m] = round(monthly_energy[m] * 0.581, 2)
                offset += hours

        hourly_energy = [round(e, 2) for e in hourly_energy]

        _update_db_progress(simulation_result_id, 90)
        _publish_progress(r, simulation_result_id, 90, "running", "正在保存结果")

        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if not result:
                raise ValueError("SimulationResult disappeared during task execution")
            result.status = "completed"
            result.progress = 100
            result.completed_at = datetime.now(timezone.utc)
            result.hourly_cooling_load = hourly_cooling
            result.hourly_heating_load = hourly_heating
            result.hourly_energy = hourly_energy
            result.total_cooling_load = total_cooling
            result.total_heating_load = total_heating
            result.total_energy = round(total_energy, 2)
            result.total_cost = round(total_cost, 2)
            result.total_carbon = round(total_carbon, 2)
            result.peak_cooling_load = peak_cooling
            result.peak_heating_load = peak_heating
            result.result_data = {
                "electricity_cost": round(total_cost, 2),
                "monthly_cost": [round(c, 2) for c in monthly_cost],
                "monthly_carbon": [round(c, 2) for c in monthly_carbon],
                "monthly_energy": [round(e, 2) for e in monthly_energy],
                "carbon_factor": 0.581,
            }
            db.commit()

        _publish_progress(r, simulation_result_id, 100, "completed", "仿真完成")
        log.info("Simulation %s completed successfully", simulation_result_id)
        return {"status": "completed", "simulation_result_id": simulation_result_id}

    except Exception as exc:
        log.exception("Simulation task %s failed: %s", simulation_result_id, exc)
        _mark_failed(simulation_result_id, exc, r)

        if self.request.retries < self.max_retries:
            with SyncSession() as db:
                result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
                if result:
                    result.status = "pending"
                    result.error_message = f"重试中 ({self.request.retries + 1}/{self.max_retries}): {str(exc)[:500]}"
                    db.commit()
            raise self.retry(exc=exc)
        raise
