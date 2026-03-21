"""Air-cooled module system model (风冷模块系统)."""

from app.simulation.systems.base import (
    HVACSystemModel,
    SimulationInput,
    SimulationOutput,
)


class AirCooledSystem(HVACSystemModel):
    """Air-cooled heat pump module system."""

    @property
    def system_type(self) -> str:
        return "air_cooled"

    def simulate(self, input_data: SimulationInput) -> SimulationOutput:
        cooling_cop = self.spec.cop or 3.2
        heating_cop = self.spec.parameters.get("heating_cop", 3.0)

        hourly_energy = []
        for cooling, heating in zip(
            input_data.hourly_cooling_load,
            input_data.hourly_heating_load,
            strict=True,
        ):
            energy = 0.0
            if cooling > 0:
                energy += cooling / cooling_cop
            if heating > 0:
                energy += heating / heating_cop
            hourly_energy.append(energy)

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
