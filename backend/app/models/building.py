import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Uuid, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    building_type: Mapped[str] = mapped_column(String(100), nullable=False)
    total_area: Mapped[float | None] = mapped_column(Float)
    floor_count: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(200))
    climate_zone: Mapped[str | None] = mapped_column(String(50))
    envelope_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="buildings")
    hvac_systems: Mapped[list["HVACSystem"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )
    simulation_results: Mapped[list["SimulationResult"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Building {self.name}>"


from app.models.project import Project  # noqa: E402, F811
from app.models.simulation import HVACSystem, SimulationResult  # noqa: E402
