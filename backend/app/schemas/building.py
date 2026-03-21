import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from typing import Any


class BuildingCreate(BaseModel):
    name: str = Field(..., max_length=200)
    building_type: str = Field(..., max_length=100)
    total_area: float | None = None
    floor_count: int | None = None
    location: str | None = Field(None, max_length=200)
    climate_zone: str | None = Field(None, max_length=50)
    envelope_params: dict[str, Any] | None = None


class BuildingUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    building_type: str | None = Field(None, max_length=100)
    total_area: float | None = None
    floor_count: int | None = None
    location: str | None = Field(None, max_length=200)
    climate_zone: str | None = Field(None, max_length=50)
    envelope_params: dict[str, Any] | None = None


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
