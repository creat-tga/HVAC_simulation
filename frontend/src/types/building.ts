export interface EnvelopeParams {
  wall_u_value?: number
  window_u_value?: number
  window_wall_ratio?: number
  roof_u_value?: number
  people_density?: number
  lighting_density?: number
  equipment_density?: number
}

export interface Building {
  id: string
  project_id: string
  name: string
  building_type: string
  total_area: number | null
  floor_count: number | null
  location: string | null
  climate_zone: string | null
  envelope_params: EnvelopeParams | null
  created_at: string
  updated_at: string
}

export interface BuildingCreate {
  name: string
  building_type: string
  total_area?: number
  floor_count?: number
  location?: string
  climate_zone?: string
  envelope_params?: EnvelopeParams
}

export interface BuildingUpdate {
  name?: string
  building_type?: string
  total_area?: number
  floor_count?: number
  location?: string
  climate_zone?: string
  envelope_params?: EnvelopeParams
}
