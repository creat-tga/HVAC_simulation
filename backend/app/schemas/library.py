"""Schemas for library: weather files, equipment models, building templates."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.building import BuildingZone


# ---------- Weather ----------

class WeatherFileResponse(BaseModel):
    id: uuid.UUID
    name: str
    province: str | None
    city: str | None
    country: str
    source: str | None
    wmo: str | None
    file_path: str
    latitude: float | None
    longitude: float | None
    elevation: float | None
    is_preset: bool
    owner_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeatherFileUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    province: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)


# ---------- Equipment ----------

EquipmentType = Literal[
    "chiller",
    "heat_pump",
    "air_cooled_module",
    "cooling_tower",
    "pump",
    "boiler",
    "fan",
    "other",
]


class EquipmentModelCreate(BaseModel):
    name: str = Field(..., max_length=200)
    equipment_type: EquipmentType
    brand: str | None = Field(None, max_length=100)
    model_no: str | None = Field(None, max_length=100)
    capacity: float | None = Field(None, ge=0)
    cop: float | None = Field(None, ge=0)
    parameters: dict[str, Any] | None = None
    description: str | None = None
    is_public: bool = False


class EquipmentModelUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    equipment_type: EquipmentType | None = None
    brand: str | None = Field(None, max_length=100)
    model_no: str | None = Field(None, max_length=100)
    capacity: float | None = Field(None, ge=0)
    cop: float | None = Field(None, ge=0)
    parameters: dict[str, Any] | None = None
    description: str | None = None
    is_public: bool | None = None


class EquipmentModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    equipment_type: str
    brand: str | None
    model_no: str | None
    capacity: float | None
    cop: float | None
    parameters: dict[str, Any] | None
    description: str | None
    is_public: bool
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Building Template ----------

class BuildingTemplateCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    building_type: str = Field(..., max_length=100)
    total_area: float | None = None
    floor_count: int | None = None
    climate_zone: str | None = Field(None, max_length=50)
    envelope_params: dict[str, Any] | None = None
    zones: list[BuildingZone] | None = None
    is_public: bool = False


class BuildingTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    building_type: str | None = Field(None, max_length=100)
    total_area: float | None = None
    floor_count: int | None = None
    climate_zone: str | None = Field(None, max_length=50)
    envelope_params: dict[str, Any] | None = None
    zones: list[BuildingZone] | None = None
    is_public: bool | None = None


class BuildingTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    building_type: str
    total_area: float | None
    floor_count: int | None
    climate_zone: str | None
    envelope_params: dict[str, Any] | None
    zones: list[BuildingZone] | None
    is_public: bool
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CloneTemplateToProjectRequest(BaseModel):
    project_id: uuid.UUID
    name: str | None = None  # override name


class CloneBuildingToTemplateRequest(BaseModel):
    name: str | None = None  # override name
    description: str | None = None
    is_public: bool = False
