"""Pydantic schemas for system schemes (项目级方案 + 多子系统层级)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


SubsystemType = Literal["chiller_plant", "air_cooled", "shared_tower"]
ConnectionType = Literal["direct", "parallel"]
PipeSystem = Literal["two_pipe", "four_pipe"]


# ---------- Combo ----------

class SchemeComboBase(BaseModel):
    id: uuid.UUID | None = None  # echoed back so dry-run validation can map issues to existing rows
    combo_index: int = Field(1, ge=1, le=10)
    primary_model_id: uuid.UUID | None = None
    primary_count: int = Field(1, ge=1, le=20)
    primary_factor: float = Field(0.92, ge=0.10, le=1.00)
    group_count: int = Field(1, ge=1, le=10)
    chw_pump_model_id: uuid.UUID | None = None
    chw_pump_count: int = Field(1, ge=1, le=20)
    chw_pump_backup: int = Field(0, ge=0, le=1)
    chw_connection: ConnectionType = "direct"
    chw_pump_factor: float = Field(0.77, ge=0.10, le=1.00)
    cw_pump_model_id: uuid.UUID | None = None
    cw_pump_count: int = Field(1, ge=1, le=20)
    cw_pump_backup: int = Field(0, ge=0, le=1)
    cw_connection: ConnectionType = "direct"
    cw_pump_factor: float = Field(0.77, ge=0.10, le=1.00)
    extra: dict[str, Any] | None = None


class SchemeComboResponse(SchemeComboBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ---------- Tower group ----------

class SchemeTowerGroupBase(BaseModel):
    id: uuid.UUID | None = None  # echoed back so dry-run validation can map issues to existing rows
    group_index: int = Field(1, ge=1, le=10)
    tower_model_id: uuid.UUID | None = None
    count: int = Field(1, ge=1, le=20)
    factor: float = Field(0.85, ge=0.10, le=1.00)


class SchemeTowerGroupResponse(SchemeTowerGroupBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ---------- Design parameters (per subsystem type, JSON) ----------

class ChillerPlantDesignParams(BaseModel):
    chw_supply_temp: float = Field(7.0, ge=1, le=25)
    chw_delta_temp: float = Field(5.0, ge=1, le=15)
    chw_pump_head: float = Field(35.0, ge=1, le=100)
    header_pressure_drop: float = Field(21.0, ge=1, le=100)
    cw_supply_temp: float = Field(30.0, ge=1, le=50)
    cw_delta_temp: float = Field(5.0, ge=1, le=15)
    cw_pump_head: float = Field(30.0, ge=1, le=100)


class AirCooledDesignParams(BaseModel):
    cooling_supply_temp: float = Field(7.0, ge=1, le=25)
    cooling_delta_temp: float = Field(5.0, ge=1, le=15)
    heating_supply_temp: float = Field(45.0, ge=30, le=100)
    heating_delta_temp: float = Field(5.0, ge=1, le=15)
    pipe_system: PipeSystem = "two_pipe"
    pump_head: float | None = Field(35.0, ge=1, le=100)
    header_pressure_drop: float | None = Field(21.0, ge=1, le=100)
    chw_pump_head: float | None = Field(35.0, ge=1, le=100)
    chw_header_pressure_drop: float | None = Field(21.0, ge=1, le=100)
    hw_pump_head: float | None = Field(35.0, ge=1, le=100)
    hw_header_pressure_drop: float | None = Field(21.0, ge=1, le=100)


# ---------- Subsystem ----------

class SubsystemBase(BaseModel):
    id: uuid.UUID | None = None  # echoed back so dry-run validation can map issues to existing rows
    subsystem_index: int = Field(1, ge=1, le=20)
    subsystem_type: SubsystemType
    name: str = Field(..., max_length=200)
    design_params: dict[str, Any] = Field(default_factory=dict)
    combos: list[SchemeComboBase] = Field(default_factory=list)
    tower_groups: list[SchemeTowerGroupBase] = Field(default_factory=list)


class SubsystemCreate(SubsystemBase):
    pass


class SubsystemUpdate(BaseModel):
    subsystem_index: int | None = Field(None, ge=1, le=20)
    name: str | None = Field(None, max_length=200)
    design_params: dict[str, Any] | None = None
    combos: list[SchemeComboBase] | None = None
    tower_groups: list[SchemeTowerGroupBase] | None = None


class SubsystemResponse(BaseModel):
    id: uuid.UUID
    scheme_id: uuid.UUID
    subsystem_index: int
    subsystem_type: str
    name: str
    design_params: dict[str, Any]
    combos: list[SchemeComboResponse] = Field(default_factory=list)
    tower_groups: list[SchemeTowerGroupResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


# ---------- SystemScheme ----------

class SystemSchemeCreate(BaseModel):
    name: str = Field(..., max_length=200)
    building_id: uuid.UUID
    scheme_index: int = Field(1, ge=1, le=5)
    safety_margin: float = Field(1.0, ge=0, le=1.2)
    control_strategy: dict[str, Any] = Field(default_factory=dict)
    diagram_json: dict[str, Any] = Field(default_factory=dict)
    subsystems: list[SubsystemCreate] = Field(default_factory=list)


class SystemSchemeUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    building_id: uuid.UUID | None = None
    scheme_index: int | None = Field(None, ge=1, le=5)
    safety_margin: float | None = Field(None, ge=0, le=1.2)
    control_strategy: dict[str, Any] | None = None
    diagram_json: dict[str, Any] | None = None
    subsystems: list[SubsystemCreate] | None = None  # full replace


class SystemSchemeResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    building_id: uuid.UUID
    scheme_index: int
    name: str
    control_strategy: dict[str, Any]
    diagram_json: dict[str, Any]
    safety_margin: float
    subsystems: list[SubsystemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SystemSchemeListItem(BaseModel):
    """Light-weight item for list cards on the project-level main page."""
    id: uuid.UUID
    name: str
    scheme_index: int
    project_id: uuid.UUID
    building_id: uuid.UUID
    building_name: str | None = None
    subsystem_count: int = 0
    safety_margin: float = 1.0
    cooling_capacity_total: float = 0.0
    heating_capacity_total: float = 0.0
    cooling_load_peak: float | None = None
    heating_load_peak: float | None = None
    # Annual energy simulation results (populated when energy simulation is run;
    # currently None until energy simulation module is implemented).
    annual_cooling_total: float | None = None  # kWh
    annual_heating_total: float | None = None  # kWh
    annual_energy_total: float | None = None  # kWh
    system_cop: float | None = None  # dimensionless
    annual_cost: float | None = None  # CNY
    has_error: bool = False
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Validation report ----------

class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    scheme_id: uuid.UUID | None = None
    subsystem_id: uuid.UUID | None = None
    combo_id: uuid.UUID | None = None
    field: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


# ---------- Capacity summary (per scheme) ----------

class CapacitySummary(BaseModel):
    cooling_load_peak: float | None = None
    heating_load_peak: float | None = None
    cooling_capacity_total: float = 0.0
    heating_capacity_total: float = 0.0


# ---------- Equipment search ----------

class EquipmentSearchQuery(BaseModel):
    equipment_type: str
    name: str | None = None
    capacity_min: float | None = None
    capacity_max: float | None = None
    flow_min: float | None = None
    flow_max: float | None = None
    head_min: float | None = None
    head_max: float | None = None
    efficiency_min: float | None = None
