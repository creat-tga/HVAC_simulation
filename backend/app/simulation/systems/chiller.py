"""Chiller plant system model (制冷机房系统)."""

from app.simulation.systems.base import (
    HVACSystemModel,
    SimulationInput,
    SimulationOutput,
)


class ChillerSystem(HVACSystemModel):
    """Chiller plant system with cooling towers and chilled water pumps."""

    @property
    def system_type(self) -> str:
        return "efficient_chiller_plant"

    def simulate(self, input_data: SimulationInput) -> SimulationOutput:
        cop = self.spec.cop or 5.0
        auxiliary_ratio = self.spec.parameters.get("auxiliary_ratio", 0.3)

        hourly_energy = []
        for cooling_load in input_data.hourly_cooling_load:
            if cooling_load > 0:
                chiller_energy = cooling_load / cop
                auxiliary_energy = chiller_energy * auxiliary_ratio
                hourly_energy.append(chiller_energy + auxiliary_energy)
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
