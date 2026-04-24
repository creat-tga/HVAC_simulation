// System scheme types — 项目级方案 + 子系统层级 (post-restructure)

export type SubsystemType = 'chiller_plant' | 'air_cooled' | 'shared_tower'
export type ConnectionType = 'direct' | 'parallel'
export type PipeSystem = 'two_pipe' | 'four_pipe'

// ---------------- Combo & TowerGroup ----------------

export interface SchemeCombo {
  id?: string
  combo_index: number
  primary_model_id: string | null
  primary_count: number
  primary_factor: number
  group_count: number
  chw_pump_model_id: string | null
  chw_pump_count: number
  chw_pump_backup: number
  chw_connection: ConnectionType
  chw_pump_factor: number
  cw_pump_model_id: string | null
  cw_pump_count: number
  cw_pump_backup: number
  cw_connection: ConnectionType
  cw_pump_factor: number
  extra?: Record<string, unknown> | null
}

export interface SchemeTowerGroup {
  id?: string
  group_index: number
  tower_model_id: string | null
  count: number
  factor: number
}

// ---------------- Design params ----------------

export interface ChillerPlantDesignParams {
  chw_supply_temp: number
  chw_delta_temp: number
  chw_pump_head: number
  header_pressure_drop: number
  cw_supply_temp: number
  cw_delta_temp: number
  cw_pump_head: number
}

export interface AirCooledDesignParams {
  cooling_supply_temp: number
  cooling_delta_temp: number
  heating_supply_temp: number
  heating_delta_temp: number
  pipe_system: PipeSystem
  pump_head?: number
  header_pressure_drop?: number
  chw_pump_head?: number
  chw_header_pressure_drop?: number
  hw_pump_head?: number
  hw_header_pressure_drop?: number
}

// ---------------- Subsystem ----------------

export interface Subsystem {
  id?: string
  scheme_id?: string
  subsystem_index: number
  subsystem_type: SubsystemType
  name: string
  design_params: Record<string, unknown>
  combos: SchemeCombo[]
  tower_groups: SchemeTowerGroup[]
}

// ---------------- Scheme (project-level) ----------------

export interface SystemScheme {
  id: string
  project_id: string
  building_id: string
  scheme_index: number
  name: string
  control_strategy: Record<string, unknown>
  diagram_json: Record<string, unknown>
  safety_margin: number
  subsystems: Subsystem[]
  created_at: string
  updated_at: string
}

export interface SystemSchemeCreate {
  name: string
  building_id: string
  scheme_index: number
  safety_margin?: number
  control_strategy?: Record<string, unknown>
  diagram_json?: Record<string, unknown>
  subsystems?: Subsystem[]
}

export type SystemSchemeUpdate = Partial<Omit<SystemSchemeCreate, 'building_id'>> & {
  building_id?: string
}

export interface SystemSchemeListItem {
  id: string
  name: string
  scheme_index: number
  project_id: string
  building_id: string
  building_name: string | null
  subsystem_count: number
  cooling_capacity_total: number
  heating_capacity_total: number
  cooling_load_peak: number | null
  heating_load_peak: number | null
  /** Annual cooling output (kWh). Null until energy simulation is run. */
  annual_cooling_total: number | null
  /** Annual heating output (kWh). */
  annual_heating_total: number | null
  /** Annual system energy consumption (kWh). */
  annual_energy_total: number | null
  /** System annual COP / efficiency. */
  system_cop: number | null
  /** Annual operating cost (CNY). */
  annual_cost: number | null
  has_error: boolean
  updated_at: string
}

// ---------------- Validation ----------------

export interface ValidationIssue {
  code: string
  severity: 'error' | 'warning'
  message: string
  scheme_id?: string | null
  subsystem_id?: string | null
  combo_id?: string | null
  field?: string | null
}

export interface ValidationReport {
  valid: boolean
  issues: ValidationIssue[]
}

export interface CapacitySummary {
  cooling_load_peak: number | null
  heating_load_peak: number | null
  cooling_capacity_total: number
  heating_capacity_total: number
}

// ---------------- Derived display data ----------------

export interface PumpView {
  brand: string | null
  name: string
  flow: number
  head: number
  power: number
  efficiency: number
  active_count: number
}

export interface SchemeDerivedCombo {
  id: string
  combo_index: number
  primary: { id: string; name: string; brand: string | null; model_no: string | null; series: string | null } | null
  primary_count: number
  group_count: number
  cooling_capacity: number
  heating_capacity: number
  power: number
  heating_power: number
  cop: number | null
  cop_heat: number | null
  chw_flow: number
  cw_flow: number
  evap_dp: number
  cond_dp: number
  chw_pump: PumpView | null
  cw_pump: PumpView | null
}

export interface SubsystemDerived {
  id: string
  subsystem_index: number
  subsystem_type: SubsystemType
  name: string
  cooling_capacity_total: number
  heating_capacity_total: number
  combos: SchemeDerivedCombo[]
  tower_groups: Array<{
    id: string
    group_index: number
    model: { id: string; name: string; brand: string | null; series: string | null } | null
    count: number
    flow: number
    power: number
    head: number
    inlet_temp: number
    outlet_temp: number
    wet_bulb: number
  }>
  tower_flow_total: number
}

export interface SchemeDerived {
  scheme_id: string
  cooling_capacity_total: number
  heating_capacity_total: number
  subsystems: SubsystemDerived[]
}

// ---------------- Equipment search ----------------

export interface EquipmentSearchParams {
  equipment_type: 'chiller' | 'air_cooled_module' | 'pump' | 'cooling_tower'
  name?: string
  capacity_min?: number
  capacity_max?: number
  flow_min?: number
  flow_max?: number
  head_min?: number
  head_max?: number
  efficiency_min?: number
  efficiency_max?: number
}

export interface EquipmentBrief {
  id: string
  name: string
  equipment_type: string
  brand: string | null
  model_no: string | null
  capacity: number | null
  cop: number | null
  parameters: Record<string, unknown> | null
  is_public: boolean
}

export const SUBSYSTEM_TYPE_LABELS: Record<SubsystemType, string> = {
  chiller_plant: 'scheme.types.chiller_plant',
  air_cooled: 'scheme.types.air_cooled',
  shared_tower: 'scheme.types.shared_tower',
}
