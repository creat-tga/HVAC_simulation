import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.building import Building
from app.models.simulation import SimulationResult
from app.schemas.building import BuildingCreate, BuildingUpdate


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


async def create_building(
    db: AsyncSession, project_id: uuid.UUID, data: BuildingCreate
) -> Building:
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
