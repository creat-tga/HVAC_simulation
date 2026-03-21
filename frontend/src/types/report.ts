export interface EnergyReport {
  total_cooling_load: number
  total_heating_load: number
  total_energy: number
  peak_cooling_load: number
  peak_heating_load: number
  hourly_cooling_load: number[]
  hourly_heating_load: number[]
  hourly_energy: number[]
  monthly_energy: number[]
}

export interface CostReport {
  total_cost: number
  electricity_cost: number
  gas_cost: number | null
  monthly_cost: number[]
}

export interface CarbonReport {
  total_carbon: number
  monthly_carbon: number[]
  carbon_factor: number
}
