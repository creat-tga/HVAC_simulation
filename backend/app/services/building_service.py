import uuid

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.building import Building
from app.models.simulation import SimulationResult
from app.schemas.building import BuildingCreate, BuildingUpdate

MAX_BUILDINGS_PER_PROJECT = 10


class BuildingLimitError(ValueError):
    pass


async def get_buildings(
    db: AsyncSession, project_id: uuid.UUID
) -> list[Building]:
    result = await db.execute(
        select(Building)
        .where(Building.project_id == project_id)
        .order_by(Building.created_at.desc())
    )
    return list(result.scalars().all())


async def get_building(db: AsyncSession, building_id: uuid.UUID) -> Building | None:
    return await db.get(Building, building_id)


async def count_project_buildings(db: AsyncSession, project_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Building).where(Building.project_id == project_id)
    )
    return result.scalar_one()


async def ensure_project_can_add_building(db: AsyncSession, project_id: uuid.UUID) -> None:
    if await count_project_buildings(db, project_id) >= MAX_BUILDINGS_PER_PROJECT:
        raise BuildingLimitError(f"一个工程最多建立{MAX_BUILDINGS_PER_PROJECT}个建筑")


async def create_building(
    db: AsyncSession, project_id: uuid.UUID, data: BuildingCreate
) -> Building:
    await ensure_project_can_add_building(db, project_id)
    building = Building(project_id=project_id, **data.model_dump())
    db.add(building)
    await db.commit()
    await db.refresh(building)
    return building


async def update_building(
    db: AsyncSession, building_id: uuid.UUID, data: BuildingUpdate
) -> Building | None:
    building = await db.get(Building, building_id)
    if not building:
        return None
    update_data = data.model_dump(exclude_unset=True)
    # If zones are changed, clear simulation results (they become invalid)
    if "zones" in update_data:
        await db.execute(
            delete(SimulationResult).where(SimulationResult.building_id == building_id)
        )
    for key, value in update_data.items():
        setattr(building, key, value)
    await db.commit()
    await db.refresh(building)
    return building


async def delete_building(db: AsyncSession, building_id: uuid.UUID) -> bool:
    building = await db.get(Building, building_id)
    if not building:
        return False
    await db.delete(building)
    await db.commit()
    return True
