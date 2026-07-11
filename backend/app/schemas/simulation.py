import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# HVAC System schemas
class HVACSystemCreate(BaseModel):
    system_type: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    capacity: float | None = None
    cop: float | None = None
    parameters: dict[str, Any] | None = None


class HVACSystemUpdate(BaseModel):
    system_type: str | None = Field(None, max_length=100)
    name: str | None = Field(None, max_length=200)
    capacity: float | None = None
    cop: float | None = None
    parameters: dict[str, Any] | None = None


class HVACSystemResponse(BaseModel):
    id: uuid.UUID
    building_id: uuid.UUID
    system_type: str
    name: str
    capacity: float | None
    cop: float | None
    parameters: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


# Simulation schemas
class SimulationCreate(BaseModel):
    simulation_type: str = Field(..., max_length=100)
    load_result_id: uuid.UUID | None = None  # For energy sim: reference to completed load sim


class SimulationResponse(BaseModel):
    id: uuid.UUID
    building_id: uuid.UUID
    simulation_type: str
    status: str
    task_id: str | None = None
    progress: int = 0
    error_message: str | None = None
    load_result_id: uuid.UUID | None = None
    scheme_id: uuid.UUID | None = None
    total_cooling_load: float | None = None
    total_heating_load: float | None = None
    total_energy: float | None = None
    total_cost: float | None = None
    total_carbon: float | None = None
    peak_cooling_load: float | None = None
    peak_heating_load: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SimulationDetailResponse(SimulationResponse):
    hourly_cooling_load: list[float] | None = None
    hourly_heating_load: list[float] | None = None
    hourly_energy: list[float] | None = None
    result_data: dict[str, Any] | None = None


class SimulationStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    task_id: str | None = None
    progress: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# Report schemas
class EnergyReport(BaseModel):
    total_cooling_load: float
    total_heating_load: float
    total_energy: float
    peak_cooling_load: float
    peak_heating_load: float
    hourly_cooling_load: list[float]
    hourly_heating_load: list[float]
    hourly_energy: list[float]
    monthly_energy: list[float]


class CostReport(BaseModel):
    total_cost: float
    electricity_cost: float
    gas_cost: float | None = None
    monthly_cost: list[float]


class CarbonReport(BaseModel):
    total_carbon: float
    monthly_carbon: list[float]
    carbon_factor: float


