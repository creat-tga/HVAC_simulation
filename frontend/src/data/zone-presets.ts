import type { ParamConfig } from '@/types/building'

/**
 * Zone preset configurations with full schedule-based internal gain parameters.
 * This JSON-driven config will later be managed via a backend admin panel.
 */

function sch(name: string, days: number[], hours: number[], value: number) {
  return { name, start_month: 1, start_day: 1, end_month: 12, end_day: 31, days, hours, value }
}

const WD = [1, 2, 3, 4, 5]     // weekdays
const WE = [6, 7]               // weekend
const H8_18 = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
const H10_16 = [10, 11, 12, 13, 14, 15]
const H9_17 = [9, 10, 11, 12, 13, 14, 15, 16]
const H10_22 = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
const H7_21 = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
const H_MEAL = [7, 8, 11, 12, 13, 17, 18, 19, 20]          // restaurant peak hours
const H_MEAL_WE = [8, 9, 10, 11, 12, 13, 17, 18, 19, 20]   // weekend restaurant

function pc(fixed: number, schedules: ReturnType<typeof sch>[]): ParamConfig {
  return { mode: 'scheduled', fixed_value: fixed, schedules }
}

function fixed(val: number): ParamConfig {
  return { mode: 'fixed', fixed_value: val, schedules: [] }
}

export interface ZonePresetConfig {
  people_density: ParamConfig
  lighting_density: ParamConfig
  equipment_density: ParamConfig
  fresh_air_volume: ParamConfig
  temperature?: ParamConfig
  relative_humidity?: ParamConfig
  floor_height: number
  wall_u_value: number
  window_u_value: number
  window_wall_ratio: number
  roof_u_value: number
}

export const ZONE_PRESETS: Record<string, ZonePresetConfig> = {
  office: {
    floor_height: 3.5,
    wall_u_value: 0.8, window_u_value: 2.8, window_wall_ratio: 0.4, roof_u_value: 0.6,
    people_density: pc(0.1, [
      sch('工作日', WD, H8_18, 0.1),
      sch('周末', WE, H10_16, 0.02),
    ]),
    lighting_density: pc(11, [
      sch('工作日', WD, H8_18, 11),
      sch('周末', WE, H10_16, 5),
    ]),
    equipment_density: pc(15, [
      sch('工作日', WD, H8_18, 15),
      sch('周末', WE, H10_16, 3),
    ]),
    fresh_air_volume: pc(30, [
      sch('工作日', WD, H8_18, 30),
      sch('周末', WE, H10_16, 15),
    ]),
  },

  meeting: {
    floor_height: 3.5,
    wall_u_value: 0.8, window_u_value: 2.8, window_wall_ratio: 0.35, roof_u_value: 0.6,
    people_density: pc(0.3, [
      sch('工作日', WD, H9_17, 0.3),
      sch('周末', WE, H10_16, 0.05),
    ]),
    lighting_density: pc(11, [
      sch('工作日', WD, H9_17, 11),
      sch('周末', WE, H10_16, 5),
    ]),
    equipment_density: pc(5, [
      sch('工作日', WD, H9_17, 5),
      sch('周末', WE, H10_16, 2),
    ]),
    fresh_air_volume: pc(30, [
      sch('工作日', WD, H9_17, 30),
      sch('周末', WE, H10_16, 10),
    ]),
  },

  lobby: {
    floor_height: 5.0,
    wall_u_value: 0.7, window_u_value: 2.5, window_wall_ratio: 0.5, roof_u_value: 0.5,
    people_density: pc(0.05, [
      sch('工作日', WD, H7_21, 0.05),
      sch('周末', WE, H10_22, 0.03),
    ]),
    lighting_density: pc(10, [
      sch('工作日', WD, H7_21, 10),
      sch('周末', WE, H10_22, 8),
    ]),
    equipment_density: pc(3, [
      sch('全周', [1,2,3,4,5,6,7], H7_21, 3),
    ]),
    fresh_air_volume: pc(20, [
      sch('工作日', WD, H7_21, 20),
      sch('周末', WE, H10_22, 15),
    ]),
  },

  corridor: {
    floor_height: 3.0,
    wall_u_value: 1.0, window_u_value: 3.0, window_wall_ratio: 0.2, roof_u_value: 0.7,
    people_density: fixed(0.02),
    lighting_density: pc(5, [
      sch('白天', [1,2,3,4,5,6,7], H7_21, 5),
    ]),
    equipment_density: fixed(0),
    fresh_air_volume: fixed(10),
  },

  restaurant: {
    floor_height: 3.5,
    wall_u_value: 0.7, window_u_value: 2.5, window_wall_ratio: 0.35, roof_u_value: 0.5,
    people_density: pc(0.25, [
      sch('工作日用餐', WD, H_MEAL, 0.25),
      sch('周末用餐', WE, H_MEAL_WE, 0.3),
    ]),
    lighting_density: pc(12, [
      sch('工作日', WD, H_MEAL, 12),
      sch('周末', WE, H_MEAL_WE, 12),
    ]),
    equipment_density: pc(10, [
      sch('工作日', WD, H_MEAL, 10),
      sch('周末', WE, H_MEAL_WE, 10),
    ]),
    fresh_air_volume: pc(25, [
      sch('工作日', WD, H_MEAL, 25),
      sch('周末', WE, H_MEAL_WE, 25),
    ]),
  },

  parking: {
    floor_height: 3.0,
    wall_u_value: 1.5, window_u_value: 5.0, window_wall_ratio: 0.1, roof_u_value: 1.0,
    people_density: fixed(0.01),
    lighting_density: pc(3, [
      sch('全天', [1,2,3,4,5,6,7], H7_21, 3),
    ]),
    equipment_density: fixed(2),
    fresh_air_volume: fixed(15),
  },

  retail: {
    floor_height: 4.0,
    wall_u_value: 0.7, window_u_value: 2.5, window_wall_ratio: 0.5, roof_u_value: 0.5,
    people_density: pc(0.15, [
      sch('工作日', WD, H10_22, 0.15),
      sch('周末', WE, H10_22, 0.25),
    ]),
    lighting_density: pc(15, [
      sch('全周', [1,2,3,4,5,6,7], H10_22, 15),
    ]),
    equipment_density: pc(8, [
      sch('全周', [1,2,3,4,5,6,7], H10_22, 8),
    ]),
    fresh_air_volume: pc(20, [
      sch('工作日', WD, H10_22, 20),
      sch('周末', WE, H10_22, 25),
    ]),
  },
}

export const PRESET_KEYS = Object.keys(ZONE_PRESETS)
