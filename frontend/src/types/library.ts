// Library types: weather, equipment, building templates

import type { BuildingZone } from '@/types/building'

export interface WeatherFile {
  id: string
  name: string
  province: string | null
  city: string | null
  country: string
  source: string | null
  wmo: string | null
  file_path: string
  latitude: number | null
  longitude: number | null
  elevation: number | null
  is_preset: boolean
  owner_id: string | null
  created_at: string
}

export type EquipmentType =
  | 'chiller'
  | 'heat_pump'
  | 'cooling_tower'
  | 'pump'
  | 'boiler'
  | 'fan'
  | 'other'

export interface EquipmentModel {
  id: string
  name: string
  equipment_type: EquipmentType
  brand: string | null
  model_no: string | null
  capacity: number | null
  cop: number | null
  parameters: Record<string, unknown> | null
  description: string | null
  is_public: boolean
  owner_id: string | null
  created_at: string
  updated_at: string
}

export interface EquipmentModelCreate {
  name: string
  equipment_type: EquipmentType
  brand?: string
  model_no?: string
  capacity?: number
  cop?: number
  parameters?: Record<string, unknown>
  description?: string
  is_public?: boolean
}

export interface BuildingTemplate {
  id: string
  name: string
  description: string | null
  building_type: string
  total_area: number | null
  floor_count: number | null
  climate_zone: string | null
  envelope_params: Record<string, unknown> | null
  zones: BuildingZone[] | null
  is_public: boolean
  owner_id: string | null
  created_at: string
  updated_at: string
}

export interface BuildingTemplateCreate {
  name: string
  description?: string
  building_type: string
  total_area?: number
  floor_count?: number
  climate_zone?: string
  envelope_params?: Record<string, unknown>
  zones?: BuildingZone[]
  is_public?: boolean
}
