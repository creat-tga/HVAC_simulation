export interface HVACSystem {
  id: string
  building_id: string
  system_type: string
  name: string
  capacity: number | null
  cop: number | null
  parameters: Record<string, unknown> | null
  created_at: string
}

export interface HVACSystemCreate {
  system_type: string
  name: string
  capacity?: number
  cop?: number
  parameters?: Record<string, unknown>
}

export interface HVACSystemUpdate {
  system_type?: string
  name?: string
  capacity?: number
  cop?: number
  parameters?: Record<string, unknown>
}

export interface SimulationResult {
  id: string
  building_id: string
  simulation_type: string
  status: string
  task_id: string | null
  progress: number
  error_message: string | null
  total_cooling_load: number | null
  total_heating_load: number | null
  total_energy: number | null
  total_cost: number | null
  total_carbon: number | null
  peak_cooling_load: number | null
  peak_heating_load: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface SimulationDetail extends SimulationResult {
  hourly_cooling_load: number[] | null
  hourly_heating_load: number[] | null
  hourly_energy: number[] | null
  result_data: Record<string, unknown> | null
}

export interface SimulationCreate {
  simulation_type: string
}

export interface SimulationStatus {
  id: string
  status: string
  task_id: string | null
  progress: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export interface SimulationProgressEvent {
  id: string
  progress: number
  status: string
  message: string
}

export interface LoadPreview {
  hourly_cooling_load: number[]
  hourly_heating_load: number[]
  total_cooling_load: number
  total_heating_load: number
  peak_cooling_load: number
  peak_heating_load: number
}

export type SystemType = 'efficient_chiller_plant' | 'air_cooled_system' | 'gshp_system'

export const SYSTEM_TYPE_LABELS: Record<SystemType, string> = {
  efficient_chiller_plant: '高效机房系统',
  air_cooled_system: '风冷系统',
  gshp_system: '地源热泵系统',
}
