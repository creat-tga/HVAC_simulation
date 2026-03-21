import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.simulation import EnergyReport, CostReport, CarbonReport
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["报表分析"])


@router.get("/energy/{result_id}", response_model=EnergyReport)
async def get_energy_report(
    result_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取用能分析报表"""
    return await report_service.get_energy_report(db, result_id)


@router.get("/cost/{result_id}", response_model=CostReport)
async def get_cost_report(
    result_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取运行费用分析报表"""
    return await report_service.get_cost_report(db, result_id)


@router.get("/carbon/{result_id}", response_model=CarbonReport)
async def get_carbon_report(
    result_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """获取碳排放分析报表"""
    return await report_service.get_carbon_report(db, result_id)
