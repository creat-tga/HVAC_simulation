import type { BuildingZone, ParamConfig } from '@/types/building'
import { ZONE_PRESETS } from '@/data/zone-presets'

export function createParamConfig(val: number): ParamConfig {
  return { mode: 'fixed', fixed_value: val, schedules: [] }
}

export function createDefaultZone(name?: string): BuildingZone {
  const preset = ZONE_PRESETS.office
  return {
    name: name || '',
    area: 100,
    floor_height: preset.floor_height,
    zone_position: 'single',
    wall_config: { south_exterior: true, north_exterior: true, east_exterior: true, west_exterior: true },
    wall_u_value: preset.wall_u_value,
    window_u_value: preset.window_u_value,
    window_wall_ratio: preset.window_wall_ratio,
    roof_u_value: preset.roof_u_value,
    people_density: createParamConfig(preset.people_density.fixed_value),
    lighting_density: createParamConfig(preset.lighting_density.fixed_value),
    equipment_density: createParamConfig(preset.equipment_density.fixed_value),
    fresh_air_volume: createParamConfig(preset.fresh_air_volume.fixed_value),
    temperature: createParamConfig(26),
    relative_humidity: createParamConfig(50),
  }
}
