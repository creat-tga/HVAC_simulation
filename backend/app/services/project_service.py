import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.building import Building
from app.schemas.project import ProjectCreate, ProjectUpdate


async def get_projects(db: AsyncSession) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    return await db.get(Project, project_id)


async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, data: ProjectUpdate
) -> Project | None:
    project = await db.get(Project, project_id)
    if not project:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> bool:
    project = await db.get(Project, project_id)
    if not project:
        return False
    await db.delete(project)
    await db.commit()
    return True


async def batch_delete_projects(db: AsyncSession, project_ids: list[uuid.UUID]) -> int:
    count = 0
    for pid in project_ids:
        project = await db.get(Project, pid)
        if project:
            await db.delete(project)
            count += 1
    await db.commit()
    return count


async def copy_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    stmt = select(Project).options(selectinload(Project.buildings)).where(Project.id == project_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        return None
    new_project = Project(
        name=f"{source.name} (副本)",
        description=source.description,
        location=source.location,
    )
    db.add(new_project)
    await db.flush()
    for b in source.buildings:
        new_building = Building(
            project_id=new_project.id,
            name=b.name,
            building_type=b.building_type,
            total_area=b.total_area,
            floor_count=b.floor_count,
            location=b.location,
            climate_zone=b.climate_zone,
            envelope_params=b.envelope_params,
        )
        db.add(new_building)
    await db.commit()
    await db.refresh(new_project)
    return new_project
