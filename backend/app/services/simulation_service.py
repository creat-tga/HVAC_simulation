import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Create and run a simulation: generate loads then compute system energy."""
    # Fetch building info
    building = await db.get(Building, building_id)
    if not building:
        raise ValueError("建筑不存在")

    zones = building.zones
    location = await _get_building_location(db, building)

    # Generate 8760 hourly loads
    hourly_cooling, hourly_heating = await _generate_loads(location, zones)

    total_cooling = round(sum(hourly_cooling), 2)
    total_heating = round(sum(hourly_heating), 2)
    peak_cooling = round(max(hourly_cooling), 2) if hourly_cooling else 0.0
    peak_heating = round(max(hourly_heating), 2) if hourly_heating else 0.0

    # Get HVAC systems for this building
    systems_result = await db.execute(
        select(HVACSystem).where(HVACSystem.building_id == building_id)
    )
    hvac_systems = list(systems_result.scalars().all())

    # Default electricity price
    electricity_price = 0.85  # yuan/kWh

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

            # Aggregate results from all systems
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
        # No systems configured, estimate with default COP
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

    sim_result = SimulationResult(
        building_id=building_id,
        simulation_type=data.simulation_type,
        status="completed",
        hourly_cooling_load=hourly_cooling,
        hourly_heating_load=hourly_heating,
        hourly_energy=hourly_energy,
        total_cooling_load=total_cooling,
        total_heating_load=total_heating,
        total_energy=round(total_energy, 2),
        total_cost=round(total_cost, 2),
        total_carbon=round(total_carbon, 2),
        peak_cooling_load=peak_cooling,
        peak_heating_load=peak_heating,
        result_data={
            "electricity_cost": round(total_cost, 2),
            "monthly_cost": [round(c, 2) for c in monthly_cost],
            "monthly_carbon": [round(c, 2) for c in monthly_carbon],
            "monthly_energy": [round(e, 2) for e in monthly_energy],
            "carbon_factor": 0.581,
        },
    )
    db.add(sim_result)
    await db.commit()
    await db.refresh(sim_result)
    return sim_result
