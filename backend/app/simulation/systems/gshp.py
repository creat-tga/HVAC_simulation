"""Ground source heat pump system model (地源热泵系统)."""

from app.simulation.systems.base import (
    HVACSystemModel,
    SimulationInput,
    SimulationOutput,
)


class GSHPSystem(HVACSystemModel):
    """Ground source heat pump system."""

    @property
    def system_type(self) -> str:
        return "gshp_system"

    def simulate(self, input_data: SimulationInput) -> SimulationOutput:
        cooling_cop = self.spec.cop or 5.5
        heating_cop = self.spec.parameters.get("heating_cop", 4.0)
        pump_power_ratio = self.spec.parameters.get("pump_power_ratio", 0.15)

        hourly_energy = []
        for cooling, heating in zip(
            input_data.hourly_cooling_load,
            input_data.hourly_heating_load,
            strict=True,
        ):
            energy = 0.0
            if cooling > 0:
                hp_energy = cooling / cooling_cop
                pump_energy = hp_energy * pump_power_ratio
                energy += hp_energy + pump_energy
            if heating > 0:
                hp_energy = heating / heating_cop
                pump_energy = hp_energy * pump_power_ratio
                energy += hp_energy + pump_energy
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
