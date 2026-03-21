"""Free cooling system model (自然冷却系统)."""

from app.simulation.systems.base import (
    HVACSystemModel,
    SimulationInput,
    SimulationOutput,
)


class FreeCoolingSystem(HVACSystemModel):
    """Free cooling system using outdoor air or water."""

    @property
    def system_type(self) -> str:
        return "free_cooling"

    def simulate(self, input_data: SimulationInput) -> SimulationOutput:
        # Free cooling only provides cooling, with minimal pump energy
        pump_power_ratio = self.spec.parameters.get("pump_power_ratio", 0.05)
        # Temperature threshold below which free cooling can operate (°C)
        # In a real implementation, this would use weather data
        free_cooling_fraction = self.spec.parameters.get("free_cooling_fraction", 0.3)

        hourly_energy = []
        for cooling_load in input_data.hourly_cooling_load:
            if cooling_load > 0:
                # Only pump energy when free cooling is available
                energy = cooling_load * pump_power_ratio * free_cooling_fraction
                hourly_energy.append(energy)
            else:
                hourly_energy.append(0.0)

        total_energy = sum(hourly_energy)
        total_cost = total_energy * input_data.electricity_price
        total_carbon = total_energy * input_data.carbon_factor

        monthly_energy = self._aggregate_monthly(hourly_energy)
        monthly_cost = [e * input_data.electricity_price for e in monthly_energy]
        monthly_carbon = [e * input_data.carbon_factor for e in monthly_energy]

        return SimulationOutput(
            hourly_energy=hourly_energy,
            total_energy=total_energy,
            total_cost=total_cost,
            total_carbon=total_carbon,
            monthly_energy=monthly_energy,
            monthly_cost=monthly_cost,
            monthly_carbon=monthly_carbon,
        )
