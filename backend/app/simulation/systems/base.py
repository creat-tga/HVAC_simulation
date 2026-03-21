"""Base class for HVAC system simulation models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SystemSpec:
    """HVAC system specification."""
    name: str
    capacity: float  # kW
    cop: float  # Coefficient of Performance
    parameters: dict


@dataclass
class SimulationInput:
    """Input data for system simulation."""
    hourly_cooling_load: list[float]  # 8760 hours, kW
    hourly_heating_load: list[float]  # 8760 hours, kW
    electricity_price: float  # yuan/kWh
    gas_price: float | None = None  # yuan/m³
    carbon_factor: float = 0.5810  # kgCO2/kWh (China grid average)


@dataclass
class SimulationOutput:
    """Output data from system simulation."""
    hourly_energy: list[float]  # 8760 hours, kWh
    total_energy: float  # kWh
    total_cost: float  # yuan
    total_carbon: float  # kgCO2
    monthly_energy: list[float]  # 12 months
    monthly_cost: list[float]  # 12 months
    monthly_carbon: list[float]  # 12 months


class HVACSystemModel(ABC):
    """Abstract base class for HVAC system simulation models."""

    def __init__(self, spec: SystemSpec) -> None:
        self.spec = spec

    @property
    @abstractmethod
    def system_type(self) -> str:
        """Return the system type identifier."""

    @abstractmethod
    def simulate(self, input_data: SimulationInput) -> SimulationOutput:
        """Run annual energy simulation for this system."""

    def _aggregate_monthly(self, hourly_data: list[float]) -> list[float]:
        """Aggregate 8760 hourly data into 12 monthly sums."""
        days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        monthly = []
        hour_offset = 0
        for days in days_per_month:
            hours = days * 24
            monthly.append(sum(hourly_data[hour_offset : hour_offset + hours]))
            hour_offset += hours
        return monthly
