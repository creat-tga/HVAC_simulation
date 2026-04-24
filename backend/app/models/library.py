"""Library models: weather files, equipment models, and building templates."""

import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Uuid, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WeatherFile(Base):
    """EPW weather file metadata. owner_id is NULL for preset files."""

    __tablename__ = "weather_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str] = mapped_column(String(50), nullable=False, default="CHN")
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # CSWD/TMYx
    wmo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EquipmentModel(Base):
    """Reusable equipment model: chiller / heat_pump / cooling_tower / pump / boiler."""

    __tablename__ = "equipment_models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacity: Mapped[float | None] = mapped_column(Float, nullable=True)  # kW
    cop: Mapped[float | None] = mapped_column(Float, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class _TypedEquipmentColumnsMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    cop: Mapped[float | None] = mapped_column(Float, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EquipmentChiller(_TypedEquipmentColumnsMixin, Base):
    __tablename__ = "equipment_chillers"


class EquipmentAirCooledModule(_TypedEquipmentColumnsMixin, Base):
    __tablename__ = "equipment_air_cooled_modules"


class EquipmentPump(_TypedEquipmentColumnsMixin, Base):
    __tablename__ = "equipment_pumps"


class EquipmentCoolingTower(_TypedEquipmentColumnsMixin, Base):
    __tablename__ = "equipment_cooling_towers"


class EquipmentBoiler(_TypedEquipmentColumnsMixin, Base):
    __tablename__ = "equipment_boilers"


class BuildingTemplate(Base):
    """Reusable building template — independent of any project, can be cloned into projects."""

    __tablename__ = "building_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_type: Mapped[str] = mapped_column(String(100), nullable=False)
    total_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    climate_zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    envelope_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    zones: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
