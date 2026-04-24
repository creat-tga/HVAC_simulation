"""System scheme models (项目级方案 + 多子系统层级).

Hierarchy (per latest spec):

  Project
   └── SystemScheme       (1~5 per project)
        ├── control_strategy / diagram_json (top-level placeholders)
        └── SystemSubsystem  (1~N per scheme; one of chiller_plant / air_cooled / shared_tower)
              ├── design_params (JSON)
              ├── SchemeCombo[]
              └── SchemeTowerGroup[]   (chiller_plant only)

Each scheme MUST be bound to one building whose load simulation has completed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SystemScheme(Base):
    __tablename__ = "system_schemes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    control_strategy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    diagram_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    safety_margin: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subsystems: Mapped[list["SystemSubsystem"]] = relationship(
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="SystemSubsystem.subsystem_index",
    )


class SystemSubsystem(Base):
    """A single sub-system within a scheme (chiller_plant / air_cooled / shared_tower)."""

    __tablename__ = "system_subsystems"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("system_schemes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subsystem_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subsystem_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    design_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scheme: Mapped[SystemScheme] = relationship(back_populates="subsystems")
    combos: Mapped[list["SchemeCombo"]] = relationship(
        back_populates="subsystem",
        cascade="all, delete-orphan",
        order_by="SchemeCombo.combo_index",
    )
    tower_groups: Mapped[list["SchemeTowerGroup"]] = relationship(
        back_populates="subsystem",
        cascade="all, delete-orphan",
        order_by="SchemeTowerGroup.group_index",
    )


class SchemeCombo(Base):
    """An equipment combination within a Subsystem."""

    __tablename__ = "system_scheme_combos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    subsystem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("system_subsystems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    combo_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    primary_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    primary_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    primary_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.92)

    group_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    chw_pump_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    chw_pump_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chw_pump_backup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chw_connection: Mapped[str] = mapped_column(String(20), nullable=False, default="direct")
    chw_pump_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.77)

    cw_pump_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    cw_pump_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cw_pump_backup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cw_connection: Mapped[str] = mapped_column(String(20), nullable=False, default="direct")
    cw_pump_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.77)

    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    subsystem: Mapped[SystemSubsystem] = relationship(back_populates="combos")


class SchemeTowerGroup(Base):
    """Cooling tower group within a Subsystem (chiller plant only)."""

    __tablename__ = "system_scheme_tower_groups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    subsystem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("system_subsystems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tower_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)

    subsystem: Mapped[SystemSubsystem] = relationship(back_populates="tower_groups")
