import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- Zone sub-models ----------

class DaySchedule(BaseModel):
    name: str
    start_month: int = Field(..., ge=1, le=12)
    start_day: int = Field(..., ge=1, le=31)
    end_month: int = Field(..., ge=1, le=12)
    end_day: int = Field(..., ge=1, le=31)
    days: list[int]    # 1=Mon … 7=Sun
    hours: list[int]   # 0-23
    value: float


class ParamConfig(BaseModel):
    mode: Literal["fixed", "scheduled"]
    fixed_value: float
    schedules: list[DaySchedule] = []


class WallConfig(BaseModel):
    """Per-wall exterior/interior setting."""
    south_exterior: bool = True
    north_exterior: bool = True
    east_exterior: bool = True
    west_exterior: bool = True


class BuildingZone(BaseModel):
    name: str = Field(..., max_length=50)
    area: float = Field(..., ge=0.1, le=9999.9)
    floor_height: float = Field(3.5, ge=1.0, le=100.0)
    # Zone vertical position: determines floor/roof boundary conditions
    zone_position: Literal["top", "middle", "bottom", "single"] = "single"
    # Wall exterior/interior config
    wall_config: WallConfig = WallConfig()
    # Envelope
    wall_u_value: float = 0.6
    window_u_value: float = 2.2
    window_wall_ratio: float = 0.3
    roof_u_value: float = 0.4
    # Internal gains
    people_density: ParamConfig
    lighting_density: ParamConfig
    equipment_density: ParamConfig
    fresh_air_volume: ParamConfig
    # Setpoints (optional for backward compat)
    temperature: ParamConfig = ParamConfig(mode="fixed", fixed_value=26, schedules=[])
    relative_humidity: ParamConfig = ParamConfig(mode="fixed", fixed_value=50, schedules=[])


# ---------- Building CRUD schemas ----------

class BuildingCreate(BaseModel):
    name: str = Field(..., max_length=200)
    building_type: str = Field(..., max_length=100)
    total_area: float | None = None
    floor_count: int | None = None
    location: str | None = Field(None, max_length=200)
    climate_zone: str | None = Field(None, max_length=50)
    envelope_params: dict[str, Any] | None = None
    zones: list[BuildingZone] | None = None


class BuildingUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    building_type: str | None = Field(None, max_length=100)
    total_area: float | None = None
    floor_count: int | None = None
    location: str | None = Field(None, max_length=200)
    climate_zone: str | None = Field(None, max_length=50)
    envelope_params: dict[str, Any] | None = None
    zones: list[BuildingZone] | None = None


class BuildingResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    building_type: str
    total_area: float | None
    floor_count: int | None
    location: str | None
    climate_zone: str | None
    envelope_params: dict[str, Any] | None
    zones: list[BuildingZone] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
