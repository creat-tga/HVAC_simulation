"""Platform-owned orchestration for multiSystem scheme energy runs."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.integrations.multisystem_adapter import MultiSystemPayloadError, build_multisystem_payload
from app.integrations.multisystem_client import MultiSystemClientError, multisystem_client
from app.models.building import Building
from app.models.project import Project
from app.models.simulation import SimulationResult
from app.services import library_service
from app.services import system_scheme_service
from app.simulation.energyplus.weather_utils import find_epw_for_location, parse_epw_header, parse_epw_hourly


log = logging.getLogger(__name__)
_TRACKING_TASKS: dict[str, asyncio.Task[None]] = {}
_TERMINAL = {"completed", "failed", "cancelled"}


async def create_scheme_energy_simulation(db: AsyncSession, scheme_id: uuid.UUID) -> SimulationResult:
    scheme = await system_scheme_service.get_scheme(db, scheme_id)
    if not scheme:
        raise ValueError("方案不存在")
    issues = await system_scheme_service.validate_scheme(db, scheme)
    errors = [issue.message for issue in issues if issue.severity == "error"]
    if errors:
        raise ValueError("方案校验未通过：" + "；".join(errors[:5]))

    active = await db.execute(
        select(SimulationResult).where(
            SimulationResult.scheme_id == scheme_id,
            SimulationResult.simulation_type == "scheme_energy",
            SimulationResult.status.in_(("pending", "running")),
        )
    )
    if active.scalars().first() is not None:
        raise ValueError("该方案已有正在运行的能耗仿真")

    building = await db.get(Building, scheme.building_id)
    if not building:
        raise ValueError("方案绑定的建筑不存在")
    load_result = await _latest_load_result(db, building.id)
    if not load_result:
        raise ValueError("建筑没有已完成的负荷仿真结果")
    project = await db.get(Project, building.project_id)
    weather, altitude = await _weather_data(project, building)
    equipment_map = await library_service.load_equipment_by_ids(db, _equipment_ids(scheme))
    payload = build_multisystem_payload(
        scheme=scheme,
        building=building,
        load_result=load_result,
        equipment_map=equipment_map,
        weather=weather,
        altitude=altitude,
    )

    result = SimulationResult(
        building_id=building.id,
        scheme_id=scheme.id,
        load_result_id=load_result.id,
        simulation_type="scheme_energy",
        status="pending",
        progress=0,
        result_data={
            "engine": "multiSystem",
            "adapter_version": 1,
            "scheme_updated_at": scheme.updated_at.isoformat() if scheme.updated_at else None,
            "hours": len(payload["meteorology"]),
            "system_ids": [item["id"] for item in payload["hvac_system"]],
        },
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)

    try:
        engine_task = await multisystem_client.start_energy(payload)
        simulation_id = str(engine_task.get("simulation_id") or "")
        if not simulation_id:
            raise MultiSystemClientError("multiSystem 未返回 simulation_id")
        result.task_id = simulation_id
        result.status = str(engine_task.get("status") or "pending")
        await db.commit()
        await db.refresh(result)
    except (MultiSystemClientError, MultiSystemPayloadError, ValueError) as exc:
        result.status = "failed"
        result.error_message = str(exc)[:1000]
        result.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise RuntimeError(str(exc)) from exc

    _start_tracking(result.id)
    return result


async def synchronize_scheme_energy_result(db: AsyncSession, result_id: uuid.UUID) -> SimulationResult | None:
    result = await db.get(SimulationResult, result_id)
    if not result or result.simulation_type != "scheme_energy" or not result.task_id:
        return result
    if result.status in _TERMINAL:
        return result

    try:
        remote = await multisystem_client.progress(result.task_id)
    except MultiSystemClientError as exc:
        log.warning("Failed to synchronize multiSystem task %s: %s", result.task_id, exc)
        return result

    status = str(remote.get("status") or result.status)
    progress = remote.get("progress") if isinstance(remote.get("progress"), dict) else {}
    result.status = status
    result.progress = max(0, min(100, round(float(progress.get("percentage") or 0))))
    if result.started_at is None and status == "running":
        result.started_at = datetime.now(timezone.utc)
    if status == "completed":
        await _finalize_completed(db, result)
    elif status in {"failed", "cancelled"}:
        result.error_message = str(remote.get("error") or ("仿真已取消" if status == "cancelled" else "multiSystem 仿真失败"))[:1000]
        result.completed_at = datetime.now(timezone.utc)
        metadata = dict(result.result_data or {})
        metadata["engine_error_details"] = remote.get("error_details") or []
        result.result_data = metadata
    await db.commit()
    await db.refresh(result)
    return result


async def cancel_scheme_energy_simulation(db: AsyncSession, result: SimulationResult) -> SimulationResult:
    if result.status in _TERMINAL:
        return result
    if not result.task_id:
        result.status = "cancelled"
    else:
        try:
            await multisystem_client.cancel(result.task_id)
        except MultiSystemClientError as exc:
            raise RuntimeError(str(exc)) from exc
        result.status = "cancelled"
    result.error_message = "用户取消"
    result.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(result)
    task = _TRACKING_TASKS.pop(str(result.id), None)
    if task is not None:
        task.cancel()
    return result


async def resume_scheme_energy_tasks() -> None:
    async with async_session() as db:
        rows = await db.execute(
            select(SimulationResult.id).where(
                SimulationResult.simulation_type == "scheme_energy",
                SimulationResult.status.in_(("pending", "running")),
                SimulationResult.task_id.is_not(None),
            )
        )
        for result_id in rows.scalars().all():
            _start_tracking(result_id)


async def shutdown_scheme_energy_tasks() -> None:
    tasks = list(_TRACKING_TASKS.values())
    _TRACKING_TASKS.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _start_tracking(result_id: uuid.UUID) -> None:
    key = str(result_id)
    existing = _TRACKING_TASKS.get(key)
    if existing is not None and not existing.done():
        return
    _TRACKING_TASKS[key] = asyncio.create_task(_track(result_id), name=f"multisystem-{key}")


async def _track(result_id: uuid.UUID) -> None:
    key = str(result_id)
    try:
        while True:
            async with async_session() as db:
                result = await synchronize_scheme_energy_result(db, result_id)
                if result is None or result.status in _TERMINAL:
                    return
            await asyncio.sleep(max(float(settings.multisystem_poll_interval_seconds), 0.5))
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("multiSystem tracking failed for platform result %s", result_id)
    finally:
        _TRACKING_TASKS.pop(key, None)


async def _finalize_completed(db: AsyncSession, result: SimulationResult) -> None:
    raw = await multisystem_client.simple_result(result.task_id or "")
    if str(raw.get("status") or "completed") != "completed":
        raise MultiSystemClientError(str(raw.get("error") or "multiSystem 结果未完成"))
    systems = raw.get("results") if isinstance(raw.get("results"), dict) else {}
    hourly_energy, system_details = _aggregate_energy(systems)
    load_result = await db.get(SimulationResult, result.load_result_id) if result.load_result_id else None
    project = None
    building = await db.get(Building, result.building_id)
    if building:
        project = await db.get(Project, building.project_id)
    electricity_price = 0.85
    if project and project.electricity_pricing:
        electricity_price = float(project.electricity_pricing.get("fixed_price", 0.85))
    total_energy = round(sum(hourly_energy), 2)
    monthly_energy = _aggregate_monthly(hourly_energy)
    metadata = dict(result.result_data or {})
    metadata.update({
        "engine_status": "completed",
        "system_details": system_details,
        "monthly_energy": monthly_energy,
        "monthly_cost": [round(value * electricity_price, 2) for value in monthly_energy],
        "monthly_carbon": [round(value * 0.581, 2) for value in monthly_energy],
        "electricity_cost": round(total_energy * electricity_price, 2),
        "carbon_factor": 0.581,
    })
    result.status = "completed"
    result.progress = 100
    result.hourly_energy = hourly_energy
    result.total_energy = total_energy
    result.total_cost = round(total_energy * electricity_price, 2)
    result.total_carbon = round(total_energy * 0.581, 2)
    if load_result:
        result.hourly_cooling_load = load_result.hourly_cooling_load
        result.hourly_heating_load = load_result.hourly_heating_load
        result.total_cooling_load = load_result.total_cooling_load
        result.total_heating_load = load_result.total_heating_load
        result.peak_cooling_load = load_result.peak_cooling_load
        result.peak_heating_load = load_result.peak_heating_load
    result.result_data = metadata
    result.completed_at = datetime.now(timezone.utc)


def _aggregate_energy(systems: dict[str, Any]) -> tuple[list[float], list[dict[str, Any]]]:
    total_hours = max((len(hours) for hours in systems.values() if isinstance(hours, list)), default=0)
    hourly_energy = [0.0] * total_hours
    details = []
    for system_id, hours in systems.items():
        if not isinstance(hours, list):
            continue
        energy = 0.0
        for index, hour in enumerate(hours):
            if not isinstance(hour, dict):
                continue
            power = float(hour.get("power_total") or 0.0)
            hourly_energy[index] += power
            energy += power
        details.append({"system_id": system_id, "total_energy": round(energy, 2)})
    return [round(value, 4) for value in hourly_energy], details


def _aggregate_monthly(hourly: list[float]) -> list[float]:
    days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    result = []
    offset = 0
    for count in days:
        hours = count * 24
        result.append(round(sum(hourly[offset:offset + hours]), 2))
        offset += hours
    return result


async def _latest_load_result(db: AsyncSession, building_id: uuid.UUID) -> SimulationResult | None:
    row = await db.execute(
        select(SimulationResult)
        .where(
            SimulationResult.building_id == building_id,
            SimulationResult.simulation_type == "load",
            SimulationResult.status == "completed",
        )
        .order_by(SimulationResult.created_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def _weather_data(project: Project | None, building: Building) -> tuple[dict[str, list[float]], float]:
    location_text = (project.location if project else None) or building.location
    parts = [part.strip() for part in str(location_text or "").split("-") if part.strip()]
    if not parts:
        raise ValueError("项目或建筑未设置地点")
    path, header = find_epw_for_location(parts)
    if not path:
        raise ValueError("未找到建筑所在地的气象文件")
    weather = await asyncio.to_thread(parse_epw_hourly, path)
    if not header:
        header = await asyncio.to_thread(parse_epw_header, path)
    altitude = float(header.get("elev") or header.get("elevation") or 0.0)
    return weather, altitude


def _equipment_ids(scheme: Any) -> list[uuid.UUID]:
    ids = []
    for subsystem in scheme.subsystems:
        for combo in subsystem.combos:
            ids.extend(value for value in (combo.primary_model_id, combo.chw_pump_model_id, combo.cw_pump_model_id) if value)
        ids.extend(group.tower_model_id for group in subsystem.tower_groups if group.tower_model_id)
    return ids