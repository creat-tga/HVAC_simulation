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


class SimulationResponse(BaseModel):
    id: uuid.UUID
    building_id: uuid.UUID
    simulation_type: str
    status: str
    total_cooling_load: float | None
    total_heating_load: float | None
    total_energy: float | None
    total_cost: float | None
    total_carbon: float | None
    peak_cooling_load: float | None
    peak_heating_load: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SimulationDetailResponse(SimulationResponse):
    hourly_cooling_load: list[float] | None
    hourly_heating_load: list[float] | None
    hourly_energy: list[float] | None
    result_data: dict[str, Any] | None


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


# Load Preview schema
class LoadPreviewResponse(BaseModel):
    hourly_cooling_load: list[float]
    hourly_heating_load: list[float]
    total_cooling_load: float
    total_heating_load: float
    peak_cooling_load: float
    peak_heating_load: float
    engine: str = "builtin"
