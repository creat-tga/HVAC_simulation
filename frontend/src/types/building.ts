export interface DaySchedule {
  name: string          // e.g., "工作日白天", "周末"
  start_month: number   // 1-12
  start_day: number     // 1-31
  end_month: number     // 1-12
  end_day: number       // 1-31
  days: number[]        // 1=Mon, 2=Tue, ..., 7=Sun
  hours: number[]       // 0-23, which hours have this value
  value: number         // single parameter value
}

export interface ParamConfig {
  mode: 'fixed' | 'scheduled'
  fixed_value: number
  schedules: DaySchedule[]
}

/** Zone vertical position in the building */
export type ZonePosition = 'top' | 'middle' | 'bottom' | 'single'

/** Per-wall exterior/interior setting */
export interface WallConfig {
  south_exterior: boolean
  north_exterior: boolean
  east_exterior: boolean
  west_exterior: boolean
}

export interface BuildingZone {
  name: string
  area: number
  floor_height: number
  // Zone position (determines floor/roof boundary conditions)
  zone_position: ZonePosition
  // Wall exterior/interior config
  wall_config: WallConfig
  // Envelope
  wall_u_value: number
  window_u_value: number
  window_wall_ratio: number
  roof_u_value: number
  // Internal gains with schedule support
  people_density: ParamConfig
  lighting_density: ParamConfig
  equipment_density: ParamConfig
  fresh_air_volume: ParamConfig
  // Setpoints with schedule support
  temperature: ParamConfig
  relative_humidity: ParamConfig
}

// Keep for backward compatibility
export interface EnvelopeParams {
  wall_u_value?: number
  window_u_value?: number
  window_wall_ratio?: number
  roof_u_value?: number
  people_density?: number
  lighting_density?: number
  equipment_density?: number
  fresh_air_volume?: number
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
  zones: BuildingZone[] | null
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
  zones?: BuildingZone[]
}

export interface BuildingUpdate {
  name?: string
  building_type?: string
  total_area?: number
  floor_count?: number
  location?: string
  climate_zone?: string
  envelope_params?: EnvelopeParams
  zones?: BuildingZone[]
}
