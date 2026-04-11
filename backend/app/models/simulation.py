import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, Uuid, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HVACSystem(Base):
    __tablename__ = "hvac_systems"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    system_type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity: Mapped[float | None] = mapped_column(Float)
    cop: Mapped[float | None] = mapped_column(Float)
    parameters: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    building: Mapped["Building"] = relationship(back_populates="hvac_systems")

    def __repr__(self) -> str:
        return f"<HVACSystem {self.name} ({self.system_type})>"


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    simulation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # Reference to load simulation result (for energy-only simulations)
    load_result_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("simulation_results.id", ondelete="SET NULL"), nullable=True
    )

    # --- Task tracking fields ---
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Result data ---
    hourly_cooling_load: Mapped[list | None] = mapped_column(JSON)
    hourly_heating_load: Mapped[list | None] = mapped_column(JSON)
    hourly_energy: Mapped[list | None] = mapped_column(JSON)
    total_cooling_load: Mapped[float | None] = mapped_column(Float)
    total_heating_load: Mapped[float | None] = mapped_column(Float)
    total_energy: Mapped[float | None] = mapped_column(Float)
    total_cost: Mapped[float | None] = mapped_column(Float)
    total_carbon: Mapped[float | None] = mapped_column(Float)
    peak_cooling_load: Mapped[float | None] = mapped_column(Float)
    peak_heating_load: Mapped[float | None] = mapped_column(Float)
    result_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    building: Mapped["Building"] = relationship(back_populates="simulation_results")

    def __repr__(self) -> str:
        return f"<SimulationResult {self.simulation_type} ({self.status})>"


from app.models.building import Building  # noqa: E402, F811
