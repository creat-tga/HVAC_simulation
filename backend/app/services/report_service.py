import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation import SimulationResult
from app.schemas.simulation import EnergyReport, CostReport, CarbonReport


def _generate_mock_hourly_loads() -> tuple[list[float], list[float]]:
    """Generate mock 8760 hourly cooling/heating loads for demo purposes."""
    cooling = []
    heating = []
    for h in range(8760):
        day_of_year = h // 24
        hour_of_day = h % 24
        # Seasonal pattern
        seasonal = math.sin((day_of_year - 80) / 365 * 2 * math.pi)
        # Diurnal pattern (higher during working hours)
        if 8 <= hour_of_day <= 18:
            diurnal = 0.8 + 0.2 * math.sin((hour_of_day - 8) / 10 * math.pi)
        else:
            diurnal = 0.3
        c_load = max(0, seasonal * 500 * diurnal + 50 * diurnal)
        h_load = max(0, -seasonal * 350 * diurnal + 30 * diurnal)
        cooling.append(round(c_load, 2))
        heating.append(round(h_load, 2))
    return cooling, heating


def _generate_mock_energy_report() -> EnergyReport:
    """Return a plausible mock EnergyReport."""
    cooling, heating = _generate_mock_hourly_loads()
    default_cop = 5.0
    hourly_energy = [round(c / default_cop, 2) if c > 0 else 0.0 for c in cooling]
    monthly_energy = _aggregate_monthly(hourly_energy)
    return EnergyReport(
        total_cooling_load=round(sum(cooling), 2),
        total_heating_load=round(sum(heating), 2),
        total_energy=round(sum(hourly_energy), 2),
        peak_cooling_load=round(max(cooling), 2),
        peak_heating_load=round(max(heating), 2),
        hourly_cooling_load=cooling,
        hourly_heating_load=heating,
        hourly_energy=hourly_energy,
        monthly_energy=monthly_energy,
    )


def _generate_mock_cost_report() -> CostReport:
    """Return a plausible mock CostReport."""
    price = 0.85
    monthly_energy = [1200, 800, 1500, 2800, 4500, 7200, 8500, 8200, 5800, 3200, 1600, 1000]
    total = sum(monthly_energy)
    return CostReport(
        total_cost=round(total * price, 2),
        electricity_cost=round(total * price, 2),
        gas_cost=None,
        monthly_cost=[round(e * price, 2) for e in monthly_energy],
    )


def _generate_mock_carbon_report() -> CarbonReport:
    """Return a plausible mock CarbonReport."""
    factor = 0.581
    monthly_energy = [1200, 800, 1500, 2800, 4500, 7200, 8500, 8200, 5800, 3200, 1600, 1000]
    total_carbon = round(sum(monthly_energy) * factor, 2)
    return CarbonReport(
        total_carbon=total_carbon,
        monthly_carbon=[round(e * factor, 2) for e in monthly_energy],
        carbon_factor=factor,
    )


def _aggregate_monthly(hourly_data: list[float]) -> list[float]:
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    monthly = []
    offset = 0
    for days in days_per_month:
        hours = days * 24
        monthly.append(round(sum(hourly_data[offset : offset + hours]), 2))
        offset += hours
    return monthly


async def get_energy_report(
    db: AsyncSession, result_id: uuid.UUID
) -> EnergyReport:
    sim = await db.get(SimulationResult, result_id)
    if not sim or sim.status != "completed":
        return _generate_mock_energy_report()
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


async def get_cost_report(
    db: AsyncSession, result_id: uuid.UUID
) -> CostReport:
    sim = await db.get(SimulationResult, result_id)
    if not sim or sim.status != "completed":
        return _generate_mock_cost_report()
    result_data = sim.result_data or {}
    return CostReport(
        total_cost=sim.total_cost or 0,
        electricity_cost=result_data.get("electricity_cost", 0),
        gas_cost=result_data.get("gas_cost"),
        monthly_cost=result_data.get("monthly_cost", [0] * 12),
    )


async def get_carbon_report(
    db: AsyncSession, result_id: uuid.UUID
) -> CarbonReport:
    sim = await db.get(SimulationResult, result_id)
    if not sim or sim.status != "completed":
        return _generate_mock_carbon_report()
    result_data = sim.result_data or {}
    return CarbonReport(
        total_carbon=sim.total_carbon or 0,
        monthly_carbon=result_data.get("monthly_carbon", [0] * 12),
        carbon_factor=result_data.get("carbon_factor", 0.5810),
    )
