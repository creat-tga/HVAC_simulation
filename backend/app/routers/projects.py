import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    BatchDeleteRequest,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.get("/", response_model=list[ProjectListResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """获取所有项目列表"""
    return await project_service.get_projects(db)


@router.post("/batch-delete", status_code=200)
async def batch_delete_projects(
    data: BatchDeleteRequest, db: AsyncSession = Depends(get_db)
):
    """批量删除项目"""
    count = await project_service.batch_delete_projects(db, data.ids)
    return {"deleted": count}


@router.post("/{project_id}/copy", response_model=ProjectResponse, status_code=201)
async def copy_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """复制项目（含建筑）"""
    project = await project_service.copy_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取项目详情"""
    project = await project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate, db: AsyncSession = Depends(get_db)
):
    """创建新项目"""
    return await project_service.create_project(db, data)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新项目信息"""
    project = await project_service.update_project(db, project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """删除项目"""
    if not await project_service.delete_project(db, project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
