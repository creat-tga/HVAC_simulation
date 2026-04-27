import { randomUUID } from './uuid'
import type { BuildingZone, DaySchedule } from '@/types/building'
import type {
  AirCooledStage,
  AirCooledStrategy,
  ControlStrategy,
  LoadDistributionConfig,
  LoadDistributionGroup,
  LoadDistributionMode,
  StrategyGroupStat,
  StrategyValueProfile,
  StrategyZoneSummary,
  Subsystem,
  ChillerPlantStrategy,
  ChillerStage,
  SubsystemControlStrategy,
  SubsystemDerived,
} from '@/types/system-scheme'

export function zoneKey(zone: BuildingZone | Record<string, unknown>, idx: number): string {
  const zid = (zone as Record<string, unknown>).id
  return zid ? String(zid) : `zone_${idx + 1}`
}

export function defaultRunSchedule(): DaySchedule {
  const hourly = Array.from({ length: 24 }, (_, hour) => (hour >= 8 && hour < 18 ? 100 : 0))
  return {
    name: '日程组 1',
    start_month: 6,
    start_day: 15,
    end_month: 10,
    end_day: 15,
    days: [1, 2, 3, 4, 5],
    hours: Array.from({ length: 10 }, (_, idx) => idx + 8),
    value: 1,
    hourly_ratios: hourly,
  }
}

export function defaultProfile(value: number): StrategyValueProfile {
  const fixed = round2(value)
  return {
    mode: 'fixed',
    fixed_value: fixed,
    month_values: Array(12).fill(fixed),
    load_values: Array(11).fill(fixed),
    dry_bulb_values: Array(10).fill(fixed),
    wet_bulb_values: Array(10).fill(fixed),
    constant_pressure: false,
  }
}

function round2(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100
}

function round1(value: number) {
  return Math.round((value + Number.EPSILON) * 10) / 10
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function derivedMap(derived: SubsystemDerived[] | null | undefined) {
  const subMap = new Map<string, SubsystemDerived>()
  const comboMap = new Map<string, SubsystemDerived['combos'][number]>()
  for (const sub of derived || []) {
    subMap.set(sub.id, sub)
    for (const combo of sub.combos) comboMap.set(combo.id, combo)
  }
  return { subMap, comboMap }
}

function distributePercentages(pairs: Array<{ key: string; value: number }>) {
  if (!pairs.length) return {}
  const total = pairs.reduce((acc, item) => acc + item.value, 0)
  if (total <= 0) {
    const each = round2(100 / pairs.length)
    const out = Object.fromEntries(pairs.map((item) => [item.key, each])) as Record<string, number>
    const first = pairs[0]?.key
    if (first) out[first] = round2(out[first] + (100 - Object.values(out).reduce((acc, val) => acc + val, 0)))
    return out
  }
  const out: Record<string, number> = {}
  let acc = 0
  pairs.forEach((item, idx) => {
    if (idx === pairs.length - 1) {
      out[item.key] = round2(100 - acc)
      return
    }
    const pct = round2((item.value / total) * 100)
    out[item.key] = pct
    acc += pct
  })
  return out
}

function subsystemPriorityRank(sub: Subsystem, derivedSub?: SubsystemDerived) {
  const rank: Record<string, number> = {
    free_cooling: 0,
    gshp: 1,
    heat_recovery: 2,
    chiller_plant: 3,
    air_cooled: 4,
    shared_tower: 5,
  }
  return [rank[sub.subsystem_type] ?? 99, derivedSub?.cooling_capacity_total ?? 0, sub.subsystem_index] as const
}

function defaultLoadDistribution(subsystems: Subsystem[], derived: SubsystemDerived[] | null | undefined, zones: BuildingZone[] | null | undefined): LoadDistributionConfig {
  const groupId = 'group-1'
  const { subMap } = derivedMap(derived)
  const subsystemIds = subsystems.map((sub) => sub.id).filter((id): id is string => !!id)
  const ratios = distributePercentages(
    subsystemIds.map((sid) => ({ key: sid, value: subMap.get(sid)?.cooling_capacity_total ?? 0 })),
  )
  const priorities = Object.fromEntries(
    [...subsystems]
      .sort((a, b) => {
        const ka = subsystemPriorityRank(a, a.id ? subMap.get(a.id) : undefined)
        const kb = subsystemPriorityRank(b, b.id ? subMap.get(b.id) : undefined)
        return ka[0] - kb[0] || ka[1] - kb[1] || ka[2] - kb[2]
      })
      .map((sub, idx) => [sub.id || `sub-${idx + 1}`, idx + 1]),
  ) as Record<string, number>

  return {
    mode: 'fixed_ratio',
    groups: [{ id: groupId, name: '分组1' }],
    zone_group_map: Object.fromEntries((zones || []).map((zone, idx) => [zoneKey(zone, idx), groupId])),
    subsystem_group_map: Object.fromEntries(subsystemIds.map((sid) => [sid, groupId])),
    group_settings: {
      [groupId]: {
        mode: 'fixed_ratio',
        ratios,
        priorities,
      },
    },
  }
}

export function buildDefaultLoadDistribution(
  subsystems: Subsystem[],
  derived: SubsystemDerived[] | null | undefined,
  zones: BuildingZone[] | null | undefined,
) {
  return defaultLoadDistribution(subsystems, derived, zones)
}

function defaultChillerStages(sub: Subsystem, derivedSub?: SubsystemDerived): ChillerStage[] {
  const comboMap = new Map((derivedSub?.combos || []).map((combo) => [combo.id, combo]))
  const units: Array<{ comboId: string; cooling: number }> = []
  for (const combo of sub.combos) {
    if (!combo.id) continue
    const derivedCombo = comboMap.get(combo.id)
    if (!derivedCombo) continue
    const perUnit = (derivedCombo.cooling_capacity || 0) / Math.max(combo.primary_count, 1)
    for (let i = 0; i < combo.primary_count; i += 1) {
      units.push({ comboId: combo.id, cooling: perUnit })
    }
  }
  units.sort((a, b) => a.cooling - b.cooling)
  if (!units.length) {
    return [{
      id: randomUUID(),
      combo_counts: {},
      loading_down: null,
      loading_up: null,
      cooling_capacity_total: 0,
      cooling_capacity_min: null,
      cooling_capacity_max: null,
    }]
  }
  const counts: Record<string, number> = {}
  const stageCaps: Record<string, number> = {}
  const out: ChillerStage[] = []
  units.forEach((unit, idx) => {
    counts[unit.comboId] = (counts[unit.comboId] || 0) + 1
    stageCaps[unit.comboId] = unit.cooling
    const total = round1(Object.entries(counts).reduce((acc, [cid, count]) => acc + (stageCaps[cid] || 0) * count, 0))
    const prevTotal = out.length ? out[out.length - 1].cooling_capacity_total : 0
    const down = idx === 0 ? null : round2(Math.max(30, (prevTotal * 70) / Math.max(total, 0.1)))
    const up = idx === units.length - 1 ? null : 90
    out.push({
      id: randomUUID(),
      combo_counts: { ...counts },
      loading_down: down,
      loading_up: up,
      cooling_capacity_total: total,
      cooling_capacity_min: down === null ? null : round1((total * down) / 100),
      cooling_capacity_max: up === null ? null : round1((total * up) / 100),
    })
  })
  return out
}

function defaultAirCooledStages(sub: Subsystem, derivedSub?: SubsystemDerived): AirCooledStage[] {
  const comboMap = new Map((derivedSub?.combos || []).map((combo) => [combo.id, combo]))
  const units: Array<{ comboId: string; cooling: number; heating: number }> = []
  for (const combo of sub.combos) {
    if (!combo.id) continue
    const derivedCombo = comboMap.get(combo.id)
    if (!derivedCombo) continue
    const groupCount = Math.max(combo.group_count, 1)
    const cool = (derivedCombo.cooling_capacity || 0) / groupCount
    const heat = (derivedCombo.heating_capacity || 0) / groupCount
    for (let i = 0; i < groupCount; i += 1) {
      units.push({ comboId: combo.id, cooling: cool, heating: heat })
    }
  }
  units.sort((a, b) => a.cooling - b.cooling)
  if (!units.length) {
    return [{
      id: randomUUID(),
      combo_counts: {},
      loading_down: null,
      loading_up: null,
      cooling_capacity_total: 0,
      cooling_capacity_min: null,
      cooling_capacity_max: null,
      heating_capacity_total: 0,
      heating_capacity_min: null,
      heating_capacity_max: null,
    }]
  }
  const counts: Record<string, number> = {}
  const stageCaps: Record<string, { cooling: number; heating: number }> = {}
  const out: AirCooledStage[] = []
  units.forEach((unit, idx) => {
    counts[unit.comboId] = (counts[unit.comboId] || 0) + 1
    stageCaps[unit.comboId] = { cooling: unit.cooling, heating: unit.heating }
    const totalCooling = round1(Object.entries(counts).reduce((acc, [cid, count]) => acc + (stageCaps[cid]?.cooling || 0) * count, 0))
    const totalHeating = round1(Object.entries(counts).reduce((acc, [cid, count]) => acc + (stageCaps[cid]?.heating || 0) * count, 0))
    const prevTotal = out.length ? out[out.length - 1].cooling_capacity_total : 0
    const down = idx === 0 ? null : round2(Math.max(30, (prevTotal * 70) / Math.max(totalCooling, 0.1)))
    const up = idx === units.length - 1 ? null : 90
    out.push({
      id: randomUUID(),
      combo_counts: { ...counts },
      loading_down: down,
      loading_up: up,
      cooling_capacity_total: totalCooling,
      cooling_capacity_min: down === null ? null : round1((totalCooling * down) / 100),
      cooling_capacity_max: up === null ? null : round1((totalCooling * up) / 100),
      heating_capacity_total: totalHeating,
      heating_capacity_min: down === null ? null : round1((totalHeating * down) / 100),
      heating_capacity_max: up === null ? null : round1((totalHeating * up) / 100),
    })
  })
  return out
}

function defaultSubsystemStrategy(sub: Subsystem, derivedSub?: SubsystemDerived): SubsystemControlStrategy {
  const dp = sub.design_params || {}
  if (sub.subsystem_type === 'chiller_plant') {
    return {
      subsystem_id: sub.id || randomUUID(),
      subsystem_type: sub.subsystem_type,
      run_schedules: [defaultRunSchedule()],
      water_temp: {
        chw_supply: defaultProfile(Number(dp.chw_supply_temp || 7)),
        chw_delta: defaultProfile(Number(dp.chw_delta_temp || 5)),
        approach: defaultProfile(3),
        cw_delta: defaultProfile(Number(dp.cw_delta_temp || 5)),
      },
      equipment: {
        chiller_stages: defaultChillerStages(sub, derivedSub),
        chw_pump: { min_freq: 30, max_freq: 50 },
        cw_pump: { min_freq: 30, max_freq: 50 },
        tower: { min_freq: 30, max_freq: 50, m: 1, k: 0 },
      },
    }
  }
  if (sub.subsystem_type === 'air_cooled') {
    const pipeSystem = String(dp.pipe_system || 'two_pipe')
    return {
      subsystem_id: sub.id || randomUUID(),
      subsystem_type: sub.subsystem_type,
      run_schedules: [defaultRunSchedule()],
      water_temp: {
        cooling_supply: defaultProfile(Number(dp.cooling_supply_temp || 7)),
        cooling_delta: defaultProfile(Number(dp.cooling_delta_temp || 5)),
        heating_supply: defaultProfile(Number(dp.heating_supply_temp || 45)),
        heating_delta: defaultProfile(Number(dp.heating_delta_temp || 5)),
      },
      equipment: {
        module_stages: defaultAirCooledStages(sub, derivedSub),
        ...(pipeSystem === 'four_pipe'
          ? {
            chw_pump: { min_freq: 30, max_freq: 50 },
            hw_pump: { min_freq: 30, max_freq: 50 },
          }
          : {
            pump: { min_freq: 30, max_freq: 50 },
          }),
      },
    }
  }
  return {
    subsystem_id: sub.id || randomUUID(),
    subsystem_type: 'shared_tower',
    run_schedules: [defaultRunSchedule()],
    water_temp: {},
    equipment: {},
  }
}

export function buildDefaultSubsystemStrategy(sub: Subsystem, derivedSub?: SubsystemDerived) {
  return defaultSubsystemStrategy(sub, derivedSub)
}

function ensureProfile(value: unknown, fallback: number, allowConstantPressure: boolean): StrategyValueProfile {
  if (!value || typeof value !== 'object') return defaultProfile(fallback)
  const raw = value as Partial<StrategyValueProfile>
  const base = defaultProfile(fallback)
  const mode = raw.mode && ['fixed', 'by_month', 'by_load', 'by_dry_bulb', 'by_wet_bulb', 'constant_pressure'].includes(raw.mode)
    ? raw.mode
    : 'fixed'
  if (mode === 'constant_pressure' && !allowConstantPressure) base.mode = 'fixed'
  else base.mode = mode as StrategyValueProfile['mode']
  if (typeof raw.fixed_value === 'number') base.fixed_value = round2(raw.fixed_value)
  if (Array.isArray(raw.month_values) && raw.month_values.length === 12) base.month_values = raw.month_values.map((item) => round2(Number(item || fallback)))
  if (Array.isArray(raw.load_values) && raw.load_values.length === 11) base.load_values = raw.load_values.map((item) => round2(Number(item || fallback)))
  if (Array.isArray(raw.dry_bulb_values) && raw.dry_bulb_values.length === 10) base.dry_bulb_values = raw.dry_bulb_values.map((item) => round2(Number(item || fallback)))
  if (Array.isArray(raw.wet_bulb_values) && raw.wet_bulb_values.length === 10) base.wet_bulb_values = raw.wet_bulb_values.map((item) => round2(Number(item || fallback)))
  base.constant_pressure = allowConstantPressure ? !!raw.constant_pressure : false
  return base
}

export function ensureControlStrategy(
  raw: unknown,
  subsystems: Subsystem[],
  derived: SubsystemDerived[] | null | undefined,
  zones: BuildingZone[] | null | undefined,
): ControlStrategy {
  const base = (raw && typeof raw === 'object' ? cloneJson(raw) : {}) as Partial<ControlStrategy>
  const loadDistribution = defaultLoadDistribution(subsystems, derived, zones)
  const { subMap } = derivedMap(derived)

  const ldRaw = base.load_distribution
  if (ldRaw && typeof ldRaw === 'object' && Array.isArray(ldRaw.groups) && ldRaw.groups.length) {
    const groups: LoadDistributionGroup[] = ldRaw.groups
      .filter((group): group is LoadDistributionGroup => !!group && typeof group.id === 'string')
      .map((group, idx) => ({ id: group.id, name: `分组${idx + 1}` }))
    if (groups.length) {
      const firstGroupId = groups[0].id
      const groupIds = new Set(groups.map((group) => group.id))
      loadDistribution.mode = ldRaw.mode || loadDistribution.mode
      loadDistribution.groups = groups
      loadDistribution.zone_group_map = Object.fromEntries(
        (zones || []).map((zone, idx) => {
          const key = zoneKey(zone, idx)
          const gid = ldRaw.zone_group_map?.[key]
          return [key, gid && groupIds.has(gid) ? gid : firstGroupId]
        }),
      )
      const subsystemIds = subsystems.map((sub) => sub.id).filter((id): id is string => !!id)
      loadDistribution.subsystem_group_map = Object.fromEntries(
        subsystemIds.map((sid) => {
          const gid = ldRaw.subsystem_group_map?.[sid]
          return [sid, gid && groupIds.has(gid) ? gid : firstGroupId]
        }),
      )
      const nextSettings: LoadDistributionConfig['group_settings'] = {}
      for (const group of groups) {
        const assignedSubIds = subsystemIds.filter((sid) => loadDistribution.subsystem_group_map[sid] === group.id)
        const fallbackRatios = distributePercentages(
          assignedSubIds.map((sid) => ({ key: sid, value: subMap.get(sid)?.cooling_capacity_total ?? 0 })),
        )
        const orderedSubs = [...subsystems]
          .filter((sub) => sub.id && assignedSubIds.includes(sub.id))
          .sort((a, b) => {
            const ka = subsystemPriorityRank(a, a.id ? subMap.get(a.id) : undefined)
            const kb = subsystemPriorityRank(b, b.id ? subMap.get(b.id) : undefined)
            return ka[0] - kb[0] || ka[1] - kb[1] || ka[2] - kb[2]
          })
        const fallbackPriorities = Object.fromEntries(orderedSubs.map((sub, idx) => [sub.id as string, idx + 1])) as Record<string, number>
        const rawMode = ldRaw.group_settings?.[group.id]?.mode
        const groupMode: LoadDistributionMode = rawMode && ['fixed_ratio', 'by_priority', 'other'].includes(rawMode)
          ? rawMode as LoadDistributionMode
          : (ldRaw.mode as LoadDistributionMode) || 'fixed_ratio'
        nextSettings[group.id] = {
          mode: groupMode,
          ratios: Object.fromEntries(assignedSubIds.map((sid) => [sid, round2(Number(ldRaw.group_settings?.[group.id]?.ratios?.[sid] ?? fallbackRatios[sid] ?? 0))])),
          priorities: Object.fromEntries(assignedSubIds.map((sid) => [sid, Number(ldRaw.group_settings?.[group.id]?.priorities?.[sid] ?? fallbackPriorities[sid] ?? 1)])),
        }
      }
      loadDistribution.group_settings = nextSettings
    }
  }

  const systemStrategies: Record<string, SubsystemControlStrategy> = {}
  const rawSystemStrategies = base.system_strategies && typeof base.system_strategies === 'object'
    ? base.system_strategies
    : {}
  for (const sub of subsystems) {
    const sid = sub.id
    if (!sid) continue
    const fallback = defaultSubsystemStrategy(sub, subMap.get(sid))
    const rawSub = rawSystemStrategies[sid]
    if (!rawSub || typeof rawSub !== 'object') {
      systemStrategies[sid] = fallback
      continue
    }
    const current = structuredClone(fallback)
    const rawSchedules = Array.isArray((rawSub as { run_schedules?: unknown[] }).run_schedules)
      ? (rawSub as { run_schedules: DaySchedule[] }).run_schedules
      : null
    if (rawSchedules?.length) current.run_schedules = rawSchedules.slice(0, 20)
    const rawWater = (rawSub as { water_temp?: Record<string, unknown> }).water_temp || {}
    if (current.subsystem_type === 'chiller_plant') {
      current.water_temp.chw_supply = ensureProfile(rawWater.chw_supply, current.water_temp.chw_supply.fixed_value, false)
      current.water_temp.chw_delta = ensureProfile(rawWater.chw_delta, current.water_temp.chw_delta.fixed_value, true)
      current.water_temp.approach = ensureProfile(rawWater.approach, current.water_temp.approach.fixed_value, false)
      current.water_temp.cw_delta = ensureProfile(rawWater.cw_delta, current.water_temp.cw_delta.fixed_value, true)
    } else if (current.subsystem_type === 'air_cooled') {
      current.water_temp.cooling_supply = ensureProfile(rawWater.cooling_supply, current.water_temp.cooling_supply.fixed_value, false)
      current.water_temp.cooling_delta = ensureProfile(rawWater.cooling_delta, current.water_temp.cooling_delta.fixed_value, true)
      current.water_temp.heating_supply = ensureProfile(rawWater.heating_supply, current.water_temp.heating_supply.fixed_value, false)
      current.water_temp.heating_delta = ensureProfile(rawWater.heating_delta, current.water_temp.heating_delta.fixed_value, true)
    }
    const rawEquipment = (rawSub as { equipment?: Record<string, unknown> }).equipment || {}
    if (current.subsystem_type === 'chiller_plant') {
      current.equipment = { ...current.equipment, ...rawEquipment } as ChillerPlantStrategy['equipment']
    } else if (current.subsystem_type === 'air_cooled') {
      current.equipment = { ...current.equipment, ...rawEquipment } as AirCooledStrategy['equipment']
    }
    systemStrategies[sid] = current
  }

  return {
    version: Number(base.version || 2),
    load_distribution: loadDistribution,
    system_strategies: systemStrategies,
  }
}

export function estimateZones(zones: BuildingZone[] | null | undefined, coolingPeak: number | null | undefined, heatingPeak: number | null | undefined): StrategyZoneSummary[] {
  const list = zones || []
  const totalArea = Math.max(list.reduce((acc, zone) => acc + Number(zone.area || 0), 0), 0.1)
  return list.map((zone, idx) => {
    const area = Number(zone.area || 0)
    const ratio = area / totalArea
    return {
      key: zoneKey(zone, idx),
      name: zone.name || `分区 ${idx + 1}`,
      area,
      cooling_peak_est: round1((coolingPeak || 0) * ratio),
      heating_peak_est: round1((heatingPeak || 0) * ratio),
      source: zone,
    }
  })
}

export function computeLoadGroupStats(
  strategy: ControlStrategy,
  zones: StrategyZoneSummary[],
  subsystems: Subsystem[],
  derived: SubsystemDerived[] | null | undefined,
): StrategyGroupStat[] {
  const { subMap } = derivedMap(derived)
  return strategy.load_distribution.groups.map((group) => {
    const groupZones = zones.filter((zone) => strategy.load_distribution.zone_group_map[zone.key] === group.id)
    const groupSubsystems = subsystems.filter((sub) => sub.id && strategy.load_distribution.subsystem_group_map[sub.id] === group.id)
    return {
      group_id: group.id,
      zone_count: groupZones.length,
      subsystem_count: groupSubsystems.length,
      cooling_load_est: round1(groupZones.reduce((acc, zone) => acc + zone.cooling_peak_est, 0)),
      heating_load_est: round1(groupZones.reduce((acc, zone) => acc + zone.heating_peak_est, 0)),
      cooling_capacity_total: round1(groupSubsystems.reduce((acc, sub) => acc + (sub.id ? subMap.get(sub.id)?.cooling_capacity_total || 0 : 0), 0)),
      heating_capacity_total: round1(groupSubsystems.reduce((acc, sub) => acc + (sub.id ? subMap.get(sub.id)?.heating_capacity_total || 0 : 0), 0)),
    }
  })
}

export function createLoadGroup(index: number): LoadDistributionGroup {
  return { id: randomUUID(), name: `分组${index + 1}` }
}
