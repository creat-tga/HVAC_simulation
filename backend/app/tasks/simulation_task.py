"""Celery task: run EnergyPlus simulation in the background."""

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


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _publish_progress(
    r: redis.Redis,
    result_id: str,
    progress: int,
    status: str,
    message: str = "",
) -> None:
    """Publish progress update to Redis channel and update DB."""
    payload = json.dumps({
        "id": result_id,
        "progress": progress,
        "status": status,
        "message": message,
    })
    r.publish(f"simulation:{result_id}", payload)


def _update_db_progress(result_id: str, progress: int, status: str = "running") -> None:
    """Update progress in DB."""
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


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
    name="app.tasks.simulation_task.run_simulation_task",
)
def run_simulation_task(self, simulation_result_id: str, building_id: str) -> dict:
    """Run full EnergyPlus simulation + system energy calculation.

    Called by the API layer after creating a pending SimulationResult.
    """
    r = _get_redis()
    channel = f"simulation:{simulation_result_id}"

    def on_ep_progress(percent: int, message: str) -> None:
        _update_db_progress(simulation_result_id, percent)
        _publish_progress(r, simulation_result_id, percent, "running", message)

    try:
        # ---- Mark running ----
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

        # ---- Load building data ----
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

        # ---- Run EnergyPlus (sync) ----
        hourly_cooling, hourly_heating = _ep_runner.run_load_simulation_sync(
            zones_dict, location, on_progress=on_ep_progress
        )

        total_cooling = round(sum(hourly_cooling), 2)
        total_heating = round(sum(hourly_heating), 2)
        peak_cooling = round(max(hourly_cooling), 2) if hourly_cooling else 0.0
        peak_heating = round(max(hourly_heating), 2) if hourly_heating else 0.0

        _update_db_progress(simulation_result_id, 75)
        _publish_progress(r, simulation_result_id, 75, "running", "开始计算系统能耗")

        # ---- System energy calculation ----
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

        # ---- Save results ----
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

        # Mark failed in DB
        with SyncSession() as db:
            result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
            if result:
                result.status = "failed"
                result.error_message = str(exc)[:2000]
                result.completed_at = datetime.now(timezone.utc)
                db.commit()

        _publish_progress(r, simulation_result_id, result.progress if result else 0, "failed", str(exc)[:500])

        # Retry if retries remaining
        if self.request.retries < self.max_retries:
            # Reset status to pending before retry
            with SyncSession() as db:
                result = db.get(SimulationResult, uuid.UUID(simulation_result_id))
                if result:
                    result.status = "pending"
                    result.error_message = f"重试中 ({self.request.retries + 1}/{self.max_retries}): {str(exc)[:500]}"
                    db.commit()
            raise self.retry(exc=exc)

        raise
