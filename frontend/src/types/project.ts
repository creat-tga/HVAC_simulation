export interface TimePeriod {
  name: string
  price: number
  hours: number[]
}

export interface TierConfig {
  upper_limit: number | null
  price_mode: 'fixed' | 'time_of_use'
  price: number
  time_periods: TimePeriod[]
}

export interface ElectricityPricing {
  mode: 'fixed' | 'time_of_use' | 'tiered'
  fixed_price: number
  time_periods: TimePeriod[]
  tiers: TierConfig[]
}

export interface Project {
  id: string
  name: string
  description: string | null
  location: string | null
  electricity_pricing: ElectricityPricing | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  location?: string
  electricity_pricing?: ElectricityPricing
}

export interface ProjectUpdate {
  name?: string
  description?: string
  location?: string
  electricity_pricing?: ElectricityPricing
}
