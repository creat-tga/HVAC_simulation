import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation import SimulationResult
from app.schemas.simulation import CarbonReport, CostReport, EnergyReport


async def _completed_result(db: AsyncSession, result_id: uuid.UUID) -> SimulationResult:
    result = await db.get(SimulationResult, result_id)
    if result is None:
        raise ValueError("仿真结果不存在")
    if result.status != "completed":
        raise ValueError(f"仿真尚未完成，当前状态：{result.status}")
    return result


async def get_energy_report(db: AsyncSession, result_id: uuid.UUID) -> EnergyReport:
    sim = await _completed_result(db, result_id)
    result_data = sim.result_data or {}
    return EnergyReport(
        total_cooling_load=sim.total_cooling_load or 0,
        total_heating_load=sim.total_heating_load or 0,
        total_energy=sim.total_energy or 0,
        peak_cooling_load=sim.peak_cooling_load or 0,
        peak_heating_load=sim.peak_heating_load or 0,
        hourly_cooling_load=sim.hourly_cooling_load or [],
        hourly_heating_load=sim.hourly_heating_load or [],
        hourly_energy=sim.hourly_energy or [],
        monthly_energy=result_data.get("monthly_energy", [0] * 12),
    )


async def get_cost_report(db: AsyncSession, result_id: uuid.UUID) -> CostReport:
    sim = await _completed_result(db, result_id)
    result_data = sim.result_data or {}
    return CostReport(
        total_cost=sim.total_cost or 0,
        electricity_cost=result_data.get("electricity_cost", 0),
        gas_cost=result_data.get("gas_cost"),
        monthly_cost=result_data.get("monthly_cost", [0] * 12),
    )


async def get_carbon_report(db: AsyncSession, result_id: uuid.UUID) -> CarbonReport:
    sim = await _completed_result(db, result_id)
    result_data = sim.result_data or {}
    return CarbonReport(
        total_carbon=sim.total_carbon or 0,
        monthly_carbon=result_data.get("monthly_carbon", [0] * 12),
        carbon_factor=result_data.get("carbon_factor", 0.5810),
    )