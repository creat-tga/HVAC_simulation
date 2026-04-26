<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import draggable from 'vuedraggable'
import { RefreshRight, Plus, Delete } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import ScheduleEditor from '@/components/building/ScheduleEditor.vue'
import StrategyValueProfileEditor from './StrategyValueProfileEditor.vue'
import { randomUUID } from '@/utils/uuid'
import type { BuildingZone } from '@/types/building'
import type {
  AirCooledStage,
  CapacitySummary,
  ChillerStage,
  ControlStrategy,
  StrategyGroupStat,
  StrategyZoneSummary,
  Subsystem,
  SubsystemControlStrategy,
  SubsystemDerived,
  ValidationIssue,
} from '@/types/system-scheme'
import {
  buildDefaultLoadDistribution,
  buildDefaultSubsystemStrategy,
  computeLoadGroupStats,
  createLoadGroup,
  ensureControlStrategy,
  estimateZones,
} from '@/utils/control-strategy'

const props = defineProps<{
  modelValue: ControlStrategy
  safetyMargin: number
  subsystems: Subsystem[]
  derived: SubsystemDerived[] | null
  summary: CapacitySummary | null
  zones: BuildingZone[] | null
  issues?: ValidationIssue[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: ControlStrategy): void
  (e: 'update:safetyMargin', value: number): void
}>()

const { t } = useI18n()

const zoneSummaries = computed<StrategyZoneSummary[]>(() =>
  estimateZones(props.zones, props.summary?.cooling_load_peak, props.summary?.heating_load_peak),
)
const groupStats = computed<StrategyGroupStat[]>(() =>
  computeLoadGroupStats(props.modelValue, zoneSummaries.value, props.subsystems, props.derived),
)
const derivedSubMap = computed(() => new Map((props.derived || []).map((sub) => [sub.id, sub])))

const topIssues = computed(() =>
  (props.issues || []).filter((issue) => !issue.subsystem_id),
)

function subsystemIssues(subId?: string) {
  if (!subId) return []
  return (props.issues || []).filter((issue) => issue.subsystem_id === subId)
}

// 按消息关键字将子系统告警归类到具体板块（运行时间 / 运行水温 / 设备启停-档位 / 设备启停-频率）
function isStageIssue(msg: string): boolean {
  return /组合|档位|冷量段|加机|减机|loading|stage/i.test(msg || '')
}
function isPumpIssue(msg: string): boolean {
  return /频率|水泵|冷却塔|min_freq|max_freq/i.test(msg || '')
}
function isScheduleIssue(msg: string): boolean {
  return /日程|schedule|时段|冲突/i.test(msg || '')
}
function isWaterTempIssue(msg: string): boolean {
  return /水温|供水|温度|approach|delta/i.test(msg || '')
}
function subsystemStageIssues(subId?: string) {
  return subsystemIssues(subId).filter((i) => isStageIssue(i.message))
}
function subsystemPumpIssues(subId?: string) {
  return subsystemIssues(subId).filter((i) => isPumpIssue(i.message))
}
function subsystemScheduleIssues(subId?: string) {
  return subsystemIssues(subId).filter((i) => isScheduleIssue(i.message))
}
function subsystemWaterTempIssues(subId?: string) {
  return subsystemIssues(subId).filter((i) => isWaterTempIssue(i.message))
}
function subsystemGeneralIssues(subId?: string) {
  return subsystemIssues(subId).filter((i) =>
    !isStageIssue(i.message) && !isPumpIssue(i.message) && !isScheduleIssue(i.message) && !isWaterTempIssue(i.message),
  )
}

// ===== Strategy 子系统折叠/持久挂载（与设备选型同样套路） =====
// activeStrategySubs：当前展开项的 name 数组（el-collapse v-model）。
// 默认仅展开第 1 个子系统，避免 N 个子系统的几百个表单组件全部
// 一次性挂载（实测 376 个 input → 1.5s+ 首屏阻塞）。
// strategyMountedSubs：持久挂载集合，子系统首次展开后保留 DOM，
// 之后再折叠/展开仅切换 el-collapse 内置的 v-show，避免重复挂载。
const activeStrategySubs = ref<string[]>([])
const strategyMountedSubs = ref<Set<string>>(new Set())
function subStrategyName(sub: { id?: string; subsystem_index: number }): string {
  return sub.id || String(sub.subsystem_index)
}
function isStrategySubMounted(sub: { id?: string; subsystem_index: number }): boolean {
  return strategyMountedSubs.value.has(subStrategyName(sub))
}
function onStrategyCollapseChange(names: string | string[] | number | (string | number)[]) {
  const list = (Array.isArray(names) ? names : [names]).map((n) => String(n))
  // 把首次展开的项加入 mountedSubs（持久挂载）。
  let changed = false
  const m = new Set(strategyMountedSubs.value)
  for (const n of list) {
    if (n && !m.has(n)) {
      m.add(n)
      changed = true
    }
  }
  if (changed) {
    // 让箭头/折叠动画先完成一帧再挂载重组件。
    requestAnimationFrame(() => {
      strategyMountedSubs.value = m
    })
  }
}
// 首次进入 strategy 步骤时自动展开第一个子系统（编辑入口）。
watch(
  () => props.subsystems,
  (subs) => {
    if (!subs?.length) return
    if (activeStrategySubs.value.length === 0) {
      const first = subStrategyName(subs[0])
      activeStrategySubs.value = [first]
      strategyMountedSubs.value = new Set([first])
    }
  },
  { immediate: true },
)

// ===== schedule conflict detection (binary on/off, same hour overlap) =====
function dateRangeOverlap(a: { start_month: number; start_day: number; end_month: number; end_day: number }, b: typeof a) {
  const toDay = (m: number, d: number) => m * 31 + d
  const aS = toDay(a.start_month, a.start_day), aE = toDay(a.end_month, a.end_day)
  const bS = toDay(b.start_month, b.start_day), bE = toDay(b.end_month, b.end_day)
  return aS <= bE && bS <= aE
}
function scheduleConflictMessage(schedules: Array<{ start_month: number; start_day: number; end_month: number; end_day: number; days?: number[]; hourly_ratios?: number[] }>, idx: number): string {
  const cur = schedules[idx]
  if (!cur) return ''
  const curOn = (cur.hourly_ratios || []).map((v) => (v ?? 0) >= 50)
  const conflicts: number[] = []
  for (let j = 0; j < schedules.length; j++) {
    if (j === idx) continue
    const other = schedules[j]
    if (!dateRangeOverlap(cur, other)) continue
    const sharedDays = (cur.days || []).some((d) => (other.days || []).includes(d))
    if (!sharedDays) continue
    const otherOn = (other.hourly_ratios || []).map((v) => (v ?? 0) >= 50)
    const conflictHours: number[] = []
    for (let h = 0; h < 24; h++) if (curOn[h] && otherOn[h]) conflictHours.push(h)
    if (conflictHours.length > 0) conflicts.push(j + 1)
  }
  if (conflicts.length === 0) return ''
  return `与日程组 ${conflicts.join('、')} 在相同小时存在重复开启`
}

// ===== derived combo label (e.g. "格力 CE1200 × 1") for stage table header =====
function derivedComboLabel(subId: string | undefined, comboId: string | undefined): string {
  if (!subId || !comboId) return ''
  const derived = derivedSubMap.value.get(subId)
  const combo = derived?.combos.find((c) => c.id === comboId)
  if (!combo || !combo.primary) return ''
  const name = combo.primary.name || combo.primary.model_no || ''
  const count = combo.primary_count || 1
  const unitCap = (combo.cooling_capacity || 0) / Math.max(count, 1)
  return `${unitCap.toFixed(1)} × ${count}`
}

// ===== combo header model name (e.g. "格力 CGW1200") =====
function comboModelName(subId: string | undefined, comboId: string | undefined): string {
  if (!subId || !comboId) return ''
  const derived = derivedSubMap.value.get(subId)
  const combo = derived?.combos.find((c) => c.id === comboId)
  if (!combo || !combo.primary) return ''
  const p = combo.primary
  const brand = p.brand ? `${p.brand} ` : ''
  const model = p.model_no || p.name || ''
  return `${brand}${model}`.trim()
}

// ===== combo header capacity subtitle (e.g. "1200 kW × 5") =====
function comboCapacitySub(subId: string | undefined, comboId: string | undefined): string {
  if (!subId || !comboId) return ''
  const derived = derivedSubMap.value.get(subId)
  const combo = derived?.combos.find((c) => c.id === comboId)
  if (!combo || !combo.primary) return ''
  const count = combo.primary_count || 1
  const unitCap = (combo.cooling_capacity || 0) / Math.max(count, 1)
  return `${unitCap.toFixed(0)} kW × ${count}`
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function emitStrategy(next: ControlStrategy) {
  emit('update:modelValue', ensureControlStrategy(next, props.subsystems, props.derived, props.zones))
}

function updateStrategy(mutator: (next: ControlStrategy) => void) {
  const next = cloneJson(props.modelValue)
  mutator(next)
  emitStrategy(next)
}

function updateSafetyMargin(value: number | null | undefined) {
  emit('update:safetyMargin', Number(value || 0))
}

function assignedSubsystemIds(groupId: string) {
  return props.subsystems
    .map((sub) => sub.id)
    .filter((id): id is string => !!id && props.modelValue.load_distribution.subsystem_group_map[id] === groupId)
}

function refreshGroupSettings(next: ControlStrategy) {
  const fallback = buildDefaultLoadDistribution(props.subsystems, props.derived, props.zones)
  const validGroupIds = new Set(next.load_distribution.groups.map((group) => group.id))
  next.load_distribution.group_settings = Object.fromEntries(
    next.load_distribution.groups.map((group) => {
      const assignedIds = props.subsystems
        .map((sub) => sub.id)
        .filter((id): id is string => !!id && next.load_distribution.subsystem_group_map[id] === group.id)
      const fallbackSetting = fallback.group_settings[group.id]
        || {
          ratios: Object.fromEntries(assignedIds.map((id) => [id, 0])),
          priorities: Object.fromEntries(assignedIds.map((id, idx) => [id, idx + 1])),
        }
      const current = next.load_distribution.group_settings[group.id] || fallbackSetting
      const preservedMode = (current as { mode?: string }).mode
      const isValidMode = preservedMode === 'fixed_ratio' || preservedMode === 'by_priority' || preservedMode === 'other'
      return [group.id, {
        mode: isValidMode ? preservedMode as 'fixed_ratio' | 'by_priority' | 'other' : (next.load_distribution.mode || 'fixed_ratio'),
        ratios: Object.fromEntries(assignedIds.map((id) => [id, Number(current.ratios?.[id] ?? fallbackSetting.ratios[id] ?? 0)])),
        priorities: Object.fromEntries(assignedIds.map((id, idx) => [id, Number(current.priorities?.[id] ?? fallbackSetting.priorities[id] ?? idx + 1)])),
      }]
    }),
  )
  next.load_distribution.zone_group_map = Object.fromEntries(
    Object.entries(next.load_distribution.zone_group_map).map(([key, value]) => [key, validGroupIds.has(value) ? value : next.load_distribution.groups[0]?.id || value]),
  )
  next.load_distribution.subsystem_group_map = Object.fromEntries(
    Object.entries(next.load_distribution.subsystem_group_map).map(([key, value]) => [key, validGroupIds.has(value) ? value : next.load_distribution.groups[0]?.id || value]),
  )
}

function recomputeGroupDefaults(next: ControlStrategy, groupId: string) {
  const setting = next.load_distribution.group_settings[groupId]
  if (!setting) return
  const assignedIds = props.subsystems
    .map((sub) => sub.id)
    .filter((id): id is string => !!id && next.load_distribution.subsystem_group_map[id] === groupId)
  if (!assignedIds.length) {
    setting.ratios = {}
    setting.priorities = {}
    return
  }
  const subRank: Record<string, number> = {
    free_cooling: 0,
    gshp: 1,
    heat_recovery: 2,
    chiller_plant: 3,
    air_cooled: 4,
    shared_tower: 5,
  }
  const weights = assignedIds.map((sid) => {
    const cap = derivedSubMap.value.get(sid)?.cooling_capacity_total ?? 0
    return { sid, weight: cap }
  })
  const total = weights.reduce((acc, w) => acc + w.weight, 0)
  const ratios: Record<string, number> = {}
  if (total <= 0) {
    const each = Math.round((100 / weights.length) * 100) / 100
    weights.forEach((w) => { ratios[w.sid] = each })
    const sum = Object.values(ratios).reduce((acc, v) => acc + v, 0)
    ratios[weights[0].sid] = Math.round((ratios[weights[0].sid] + (100 - sum)) * 100) / 100
  } else {
    let acc = 0
    weights.forEach((w, idx) => {
      if (idx === weights.length - 1) {
        ratios[w.sid] = Math.round((100 - acc) * 100) / 100
      } else {
        const pct = Math.round((w.weight / total) * 100 * 100) / 100
        ratios[w.sid] = pct
        acc += pct
      }
    })
  }
  const ordered = [...assignedIds].sort((a, b) => {
    const sa = props.subsystems.find((s) => s.id === a)
    const sb = props.subsystems.find((s) => s.id === b)
    const ra = sa ? (subRank[sa.subsystem_type] ?? 99) : 99
    const rb = sb ? (subRank[sb.subsystem_type] ?? 99) : 99
    if (ra !== rb) return ra - rb
    const ca = derivedSubMap.value.get(a)?.cooling_capacity_total ?? 0
    const cb = derivedSubMap.value.get(b)?.cooling_capacity_total ?? 0
    return cb - ca
  })
  setting.ratios = ratios
  setting.priorities = Object.fromEntries(ordered.map((sid, idx) => [sid, idx + 1]))
}

function addGroup() {
  updateStrategy((next) => {
    const group = createLoadGroup(next.load_distribution.groups.length)
    next.load_distribution.groups.push(group)
    next.load_distribution.group_settings[group.id] = { ratios: {}, priorities: {} }
    refreshGroupSettings(next)
  })
}

function removeGroup(groupId: string) {
  updateStrategy((next) => {
    if (next.load_distribution.groups.length <= 1) return
    const remain = next.load_distribution.groups.filter((group) => group.id !== groupId)
    const fallbackId = remain[0]?.id
    next.load_distribution.groups = remain
    if (fallbackId) {
      Object.keys(next.load_distribution.zone_group_map).forEach((key) => {
        if (next.load_distribution.zone_group_map[key] === groupId) next.load_distribution.zone_group_map[key] = fallbackId
      })
      Object.keys(next.load_distribution.subsystem_group_map).forEach((key) => {
        if (next.load_distribution.subsystem_group_map[key] === groupId) next.load_distribution.subsystem_group_map[key] = fallbackId
      })
    }
    delete next.load_distribution.group_settings[groupId]
    refreshGroupSettings(next)
  })
}

function resetLoadDistribution() {
  emitStrategy({
    ...props.modelValue,
    load_distribution: buildDefaultLoadDistribution(props.subsystems, props.derived, props.zones),
  })
}

function updateGroupName(groupId: string, name: string) {
  updateStrategy((next) => {
    const group = next.load_distribution.groups.find((item) => item.id === groupId)
    if (group) group.name = name
  })
}

function updateZoneGroup(zoneKeyValue: string, groupId: string) {
  updateStrategy((next) => {
    next.load_distribution.zone_group_map[zoneKeyValue] = groupId
    refreshGroupSettings(next)
  })
}

function updateSubsystemGroup(subsystemId: string, groupId: string) {
  const previousGroupId = props.modelValue.load_distribution.subsystem_group_map[subsystemId]
  updateStrategy((next) => {
    next.load_distribution.subsystem_group_map[subsystemId] = groupId
    refreshGroupSettings(next)
    recomputeGroupDefaults(next, groupId)
    if (previousGroupId && previousGroupId !== groupId) recomputeGroupDefaults(next, previousGroupId)
  })
}

function updateRatio(groupId: string, subsystemId: string, value: number) {
  updateStrategy((next) => {
    next.load_distribution.group_settings[groupId] ||= { ratios: {}, priorities: {} }
    next.load_distribution.group_settings[groupId].ratios[subsystemId] = Number(value || 0)
  })
}

function updatePriority(groupId: string, subsystemId: string, value: number) {
  updateStrategy((next) => {
    next.load_distribution.group_settings[groupId] ||= { ratios: {}, priorities: {} }
    next.load_distribution.group_settings[groupId].priorities[subsystemId] = Number(value || 1)
  })
}

function sortedPriorityIds(groupId: string): string[] {
  const ids = props.subsystems
    .map((sub) => sub.id)
    .filter((id): id is string => !!id && props.modelValue.load_distribution.subsystem_group_map[id] === groupId)
  const setting = props.modelValue.load_distribution.group_settings[groupId]
  return [...ids].sort((a, b) => Number(setting?.priorities?.[a] ?? 999) - Number(setting?.priorities?.[b] ?? 999))
}

function reorderPriorityByIndex(groupId: string, fromIdx: number, toIdx: number) {
  if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0) return
  const order = sortedPriorityIds(groupId)
  if (fromIdx >= order.length || toIdx >= order.length) return
  const next = order.slice()
  const [moved] = next.splice(fromIdx, 1)
  next.splice(toIdx, 0, moved)
  updateStrategy((draft) => {
    const setting = draft.load_distribution.group_settings[groupId] ||= { ratios: {}, priorities: {} }
    next.forEach((sid, idx) => { setting.priorities[sid] = idx + 1 })
  })
}
void reorderPriorityByIndex

function itemKeyOfSid(sid: string) { return sid }

function updateLoadMode(mode: ControlStrategy['load_distribution']['mode']) {
  updateStrategy((next) => {
    next.load_distribution.mode = mode
    refreshGroupSettings(next)
  })
}

function groupModeOf(groupId: string): ControlStrategy['load_distribution']['mode'] {
  const setting = props.modelValue.load_distribution.group_settings[groupId]
  const mode = setting?.mode
  if (mode === 'fixed_ratio' || mode === 'by_priority' || mode === 'other') return mode
  return props.modelValue.load_distribution.mode || 'fixed_ratio'
}

function updateGroupMode(groupId: string, mode: ControlStrategy['load_distribution']['mode']) {
  updateStrategy((next) => {
    next.load_distribution.group_settings[groupId] ||= { mode, ratios: {}, priorities: {} }
    next.load_distribution.group_settings[groupId].mode = mode
    refreshGroupSettings(next)
    recomputeGroupDefaults(next, groupId)
  })
}

function setGroupCount(rawCount: number | null | undefined) {
  const target = Math.max(1, Math.min(20, Math.floor(Number(rawCount || 1))))
  const current = props.modelValue.load_distribution.groups.length
  if (target === current) return
  if (target > current) {
    updateStrategy((next) => {
      while (next.load_distribution.groups.length < target) {
        const idx = next.load_distribution.groups.length
        const group = createLoadGroup(idx)
        next.load_distribution.groups.push(group)
        next.load_distribution.group_settings[group.id] = { mode: 'fixed_ratio', ratios: {}, priorities: {} }
      }
      refreshGroupSettings(next)
    })
  } else {
    updateStrategy((next) => {
      const removed = next.load_distribution.groups.slice(target).map((g) => g.id)
      const fallbackId = next.load_distribution.groups[0].id
      next.load_distribution.groups = next.load_distribution.groups.slice(0, target)
      Object.keys(next.load_distribution.zone_group_map).forEach((key) => {
        if (removed.includes(next.load_distribution.zone_group_map[key])) next.load_distribution.zone_group_map[key] = fallbackId
      })
      Object.keys(next.load_distribution.subsystem_group_map).forEach((key) => {
        if (removed.includes(next.load_distribution.subsystem_group_map[key])) next.load_distribution.subsystem_group_map[key] = fallbackId
      })
      removed.forEach((gid) => { delete next.load_distribution.group_settings[gid] })
      refreshGroupSettings(next)
    })
  }
}

function assignedZoneKeys(groupId: string): string[] {
  return zoneSummaries.value
    .map((zone) => zone.key)
    .filter((key) => props.modelValue.load_distribution.zone_group_map[key] === groupId)
}

function unassignedZoneOptions(groupId: string) {
  return zoneSummaries.value.filter((zone) => props.modelValue.load_distribution.zone_group_map[zone.key] !== groupId)
}

function unassignedSubsystemOptions(groupId: string) {
  return props.subsystems.filter((sub) => sub.id && props.modelValue.load_distribution.subsystem_group_map[sub.id] !== groupId)
}

function zoneInfo(zoneKeyValue: string) {
  return zoneSummaries.value.find((zone) => zone.key === zoneKeyValue)
}

function subInfo(subId: string) {
  return props.subsystems.find((sub) => sub.id === subId)
}

// ---- Pickers (zone/subsystem) with search + multi-select ----
const pickerSearch = reactive<Record<string, string>>({})
const pickerSelected = reactive<Record<string, string[]>>({})

function pickerKey(groupId: string, type: 'zone' | 'sub') {
  return `${groupId}::${type}`
}
function resetPicker(groupId: string, type: 'zone' | 'sub') {
  const key = pickerKey(groupId, type)
  pickerSearch[key] = ''
  pickerSelected[key] = []
}
function filteredZoneOptions(groupId: string) {
  const key = pickerKey(groupId, 'zone')
  const kw = (pickerSearch[key] || '').trim().toLowerCase()
  const list = unassignedZoneOptions(groupId)
  if (!kw) return list
  return list.filter((z) => z.name.toLowerCase().includes(kw) || z.key.toLowerCase().includes(kw))
}
function filteredSubsystemOptions(groupId: string) {
  const key = pickerKey(groupId, 'sub')
  const kw = (pickerSearch[key] || '').trim().toLowerCase()
  const list = unassignedSubsystemOptions(groupId)
  if (!kw) return list
  return list.filter((s) => (s.name || '').toLowerCase().includes(kw) || (s.id || '').toLowerCase().includes(kw))
}
function selectAllZones(groupId: string) {
  const key = pickerKey(groupId, 'zone')
  pickerSelected[key] = filteredZoneOptions(groupId).map((z) => z.key)
}
function selectAllSubsystems(groupId: string) {
  const key = pickerKey(groupId, 'sub')
  pickerSelected[key] = filteredSubsystemOptions(groupId).map((s) => s.id as string)
}
function confirmAddZones(groupId: string) {
  const key = pickerKey(groupId, 'zone')
  const ids = pickerSelected[key] || []
  if (!ids.length) return
  updateStrategy((next) => {
    ids.forEach((zk) => { next.load_distribution.zone_group_map[zk] = groupId })
    refreshGroupSettings(next)
  })
  resetPicker(groupId, 'zone')
}
function confirmAddSubsystems(groupId: string) {
  const key = pickerKey(groupId, 'sub')
  const ids = pickerSelected[key] || []
  if (!ids.length) return
  const previousGroups = new Set<string>()
  ids.forEach((sid) => {
    const prev = props.modelValue.load_distribution.subsystem_group_map[sid]
    if (prev && prev !== groupId) previousGroups.add(prev)
  })
  updateStrategy((next) => {
    ids.forEach((sid) => { next.load_distribution.subsystem_group_map[sid] = groupId })
    refreshGroupSettings(next)
    recomputeGroupDefaults(next, groupId)
    previousGroups.forEach((gid) => recomputeGroupDefaults(next, gid))
  })
  resetPicker(groupId, 'sub')
}
function removeZoneFromGroup(zoneKeyValue: string, currentGroupId: string) {
  const groups = props.modelValue.load_distribution.groups
  const fallback = groups.find((g) => g.id !== currentGroupId)?.id || groups[0]?.id
  if (!fallback) return
  updateZoneGroup(zoneKeyValue, fallback)
}
function removeSubsystemFromGroup(subsystemId: string, currentGroupId: string) {
  const groups = props.modelValue.load_distribution.groups
  const fallback = groups.find((g) => g.id !== currentGroupId)?.id || groups[0]?.id
  if (!fallback) return
  updateSubsystemGroup(subsystemId, fallback)
}
void removeSubsystemFromGroup

function getSubsystemStrategy(sub: Subsystem): SubsystemControlStrategy | null {
  if (!sub.id) return null
  return props.modelValue.system_strategies[sub.id] || null
}

function updateSubsystemStrategy(sub: Subsystem, mutator: (next: SubsystemControlStrategy) => void) {
  if (!sub.id) return
  updateStrategy((next) => {
    const current = cloneJson(next.system_strategies[sub.id]) as SubsystemControlStrategy
    mutator(current)
    next.system_strategies[sub.id] = current
  })
}

function resetSubsystemStrategy(sub: Subsystem) {
  if (!sub.id) return
  emitStrategy({
    ...props.modelValue,
    system_strategies: {
      ...props.modelValue.system_strategies,
      [sub.id]: buildDefaultSubsystemStrategy(sub, derivedSubMap.value.get(sub.id)),
    },
  })
}

function addSchedule(sub: Subsystem) {
  updateSubsystemStrategy(sub, (next) => {
    if (next.run_schedules.length >= 20) return
    next.run_schedules.push({ ...cloneJson(next.run_schedules[0] || buildDefaultSubsystemStrategy(sub, derivedSubMap.value.get(sub.id)).run_schedules[0]), name: `日程组 ${next.run_schedules.length + 1}` })
  })
}

function removeSchedule(sub: Subsystem, idx: number) {
  updateSubsystemStrategy(sub, (next) => {
    if (next.run_schedules.length <= 1) return
    next.run_schedules.splice(idx, 1)
  })
}

function updateSchedule(sub: Subsystem, idx: number, value: SubsystemControlStrategy['run_schedules'][number]) {
  updateSubsystemStrategy(sub, (next) => {
    next.run_schedules[idx] = value
  })
}

function recalcChillerStages(sub: Subsystem, stages: ChillerStage[]) {
  const derivedSub = sub.id ? derivedSubMap.value.get(sub.id) : undefined
  const comboMap = new Map((derivedSub?.combos || []).map((combo) => [combo.id, combo]))
  return stages.map((stage, idx) => {
    const total = sub.combos.reduce((acc, combo) => {
      if (!combo.id) return acc
      const unit = (comboMap.get(combo.id)?.cooling_capacity || 0) / Math.max(combo.primary_count, 1)
      return acc + unit * Number(stage.combo_counts?.[combo.id] || 0)
    }, 0)
    const prevTotal = idx > 0 ? stages[idx - 1].cooling_capacity_total : 0
    const down = idx === 0 ? null : Number(stage.loading_down ?? Math.max(30, (prevTotal * 70) / Math.max(total, 0.1)))
    const up = idx === stages.length - 1 ? null : Number(stage.loading_up ?? 90)
    return {
      ...stage,
      cooling_capacity_total: Number(total.toFixed(1)),
      loading_down: down,
      loading_up: up,
      cooling_capacity_min: down === null ? null : Number(((total * down) / 100).toFixed(1)),
      cooling_capacity_max: up === null ? null : Number(((total * up) / 100).toFixed(1)),
    }
  })
}

function recalcAirCooledStages(sub: Subsystem, stages: AirCooledStage[]) {
  const derivedSub = sub.id ? derivedSubMap.value.get(sub.id) : undefined
  const comboMap = new Map((derivedSub?.combos || []).map((combo) => [combo.id, combo]))
  return stages.map((stage, idx) => {
    let totalCooling = 0
    let totalHeating = 0
    for (const combo of sub.combos) {
      if (!combo.id) continue
      const derivedCombo = comboMap.get(combo.id)
      const groupsOn = Number(stage.combo_counts?.[combo.id] || 0)
      const perGroupCooling = (derivedCombo?.cooling_capacity || 0) / Math.max(combo.group_count, 1)
      const perGroupHeating = (derivedCombo?.heating_capacity || 0) / Math.max(combo.group_count, 1)
      totalCooling += perGroupCooling * groupsOn
      totalHeating += perGroupHeating * groupsOn
    }
    const prevTotal = idx > 0 ? stages[idx - 1].cooling_capacity_total : 0
    const down = idx === 0 ? null : Number(stage.loading_down ?? Math.max(30, (prevTotal * 70) / Math.max(totalCooling, 0.1)))
    const up = idx === stages.length - 1 ? null : Number(stage.loading_up ?? 90)
    return {
      ...stage,
      cooling_capacity_total: Number(totalCooling.toFixed(1)),
      heating_capacity_total: Number(totalHeating.toFixed(1)),
      loading_down: down,
      loading_up: up,
      cooling_capacity_min: down === null ? null : Number(((totalCooling * down) / 100).toFixed(1)),
      cooling_capacity_max: up === null ? null : Number(((totalCooling * up) / 100).toFixed(1)),
      heating_capacity_min: down === null ? null : Number(((totalHeating * down) / 100).toFixed(1)),
      heating_capacity_max: up === null ? null : Number(((totalHeating * up) / 100).toFixed(1)),
    }
  })
}

function addStage(sub: Subsystem) {
  updateSubsystemStrategy(sub, (next) => {
    const emptyCounts = Object.fromEntries(sub.combos.filter((combo) => combo.id).map((combo) => [combo.id as string, 0]))
    if (next.subsystem_type === 'chiller_plant') {
      next.equipment.chiller_stages.push({
        id: randomUUID(),
        combo_counts: emptyCounts,
        loading_down: null,
        loading_up: null,
        cooling_capacity_total: 0,
        cooling_capacity_min: null,
        cooling_capacity_max: null,
      })
      next.equipment.chiller_stages = recalcChillerStages(sub, next.equipment.chiller_stages)
    } else if (next.subsystem_type === 'air_cooled') {
      next.equipment.module_stages.push({
        id: randomUUID(),
        combo_counts: emptyCounts,
        loading_down: null,
        loading_up: null,
        cooling_capacity_total: 0,
        cooling_capacity_min: null,
        cooling_capacity_max: null,
        heating_capacity_total: 0,
        heating_capacity_min: null,
        heating_capacity_max: null,
      })
      next.equipment.module_stages = recalcAirCooledStages(sub, next.equipment.module_stages)
    }
  })
}

function removeStage(sub: Subsystem, idx: number) {
  updateSubsystemStrategy(sub, (next) => {
    if (next.subsystem_type === 'chiller_plant') {
      if (next.equipment.chiller_stages.length <= 1) return
      next.equipment.chiller_stages.splice(idx, 1)
      next.equipment.chiller_stages = recalcChillerStages(sub, next.equipment.chiller_stages)
    } else if (next.subsystem_type === 'air_cooled') {
      if (next.equipment.module_stages.length <= 1) return
      next.equipment.module_stages.splice(idx, 1)
      next.equipment.module_stages = recalcAirCooledStages(sub, next.equipment.module_stages)
    }
  })
}

function insertStageAt(sub: Subsystem, afterIdx: number) {
  updateSubsystemStrategy(sub, (next) => {
    const emptyCounts = Object.fromEntries(sub.combos.filter((combo) => combo.id).map((combo) => [combo.id as string, 0]))
    if (next.subsystem_type === 'chiller_plant') {
      next.equipment.chiller_stages.splice(afterIdx + 1, 0, {
        id: randomUUID(),
        combo_counts: emptyCounts,
        loading_down: null,
        loading_up: null,
        cooling_capacity_total: 0,
        cooling_capacity_min: null,
        cooling_capacity_max: null,
      })
      next.equipment.chiller_stages = recalcChillerStages(sub, next.equipment.chiller_stages)
    } else if (next.subsystem_type === 'air_cooled') {
      next.equipment.module_stages.splice(afterIdx + 1, 0, {
        id: randomUUID(),
        combo_counts: emptyCounts,
        loading_down: null,
        loading_up: null,
        cooling_capacity_total: 0,
        cooling_capacity_min: null,
        cooling_capacity_max: null,
        heating_capacity_total: 0,
        heating_capacity_min: null,
        heating_capacity_max: null,
      })
      next.equipment.module_stages = recalcAirCooledStages(sub, next.equipment.module_stages)
    }
  })
}

function updateStageCount(sub: Subsystem, stageIdx: number, comboId: string, value: number) {
  updateSubsystemStrategy(sub, (next) => {
    if (next.subsystem_type === 'chiller_plant') {
      next.equipment.chiller_stages[stageIdx].combo_counts[comboId] = value
      next.equipment.chiller_stages = recalcChillerStages(sub, next.equipment.chiller_stages)
    } else if (next.subsystem_type === 'air_cooled') {
      next.equipment.module_stages[stageIdx].combo_counts[comboId] = value
      next.equipment.module_stages = recalcAirCooledStages(sub, next.equipment.module_stages)
    }
  })
}

function updateStageField(sub: Subsystem, stageIdx: number, field: 'loading_down' | 'loading_up', value: number) {
  updateSubsystemStrategy(sub, (next) => {
    if (next.subsystem_type === 'chiller_plant') {
      next.equipment.chiller_stages[stageIdx][field] = value
      next.equipment.chiller_stages = recalcChillerStages(sub, next.equipment.chiller_stages)
    } else if (next.subsystem_type === 'air_cooled') {
      next.equipment.module_stages[stageIdx][field] = value
      next.equipment.module_stages = recalcAirCooledStages(sub, next.equipment.module_stages)
    }
  })
}

function updateEquipmentField(sub: Subsystem, key: string, field: string, value: number) {
  updateSubsystemStrategy(sub, (next) => {
    const equipment = next.equipment as Record<string, Record<string, number>>
    equipment[key] ||= {} as Record<string, number>
    equipment[key][field] = Number(value || 0)
  })
}
</script>

<template>
  <div class="strategy-page">
    <el-alert
      v-for="(issue, idx) in topIssues"
      :key="idx"
      :type="issue.severity === 'error' ? 'error' : 'warning'"
      :title="issue.message"
      show-icon
      :closable="false"
      class="strategy-alert"
    />

    <div class="safety-margin-bar">
      <span class="safety-margin-label">{{ t('scheme.strategy.safetyMargin') }}</span>
      <el-input-number
        :model-value="safetyMargin"
        :min="0"
        :max="1.2"
        :step="0.01"
        :precision="2"
        size="small"
        style="width: 130px;"
        @update:model-value="(val) => updateSafetyMargin(Number(val || 0))"
      />
    </div>

    <el-card class="strategy-card" shadow="never">
      <template #header>
        <div class="card-head">
          <div class="card-title">{{ t('scheme.strategy.tabLoadDist') }}</div>
          <div class="card-actions ld-actions">
            <span class="ld-count-label">{{ t('scheme.strategy.groupCount') }}</span>
            <el-input-number
              :model-value="modelValue.load_distribution.groups.length"
              :min="1"
              :max="20"
              :step="1"
              size="small"
              @update:model-value="(val) => setGroupCount(Number(val))"
            />
            <el-button size="small" :icon="RefreshRight" @click="resetLoadDistribution">{{ t('scheme.strategy.resetDefault') }}</el-button>
          </div>
        </div>
      </template>

      <div class="ld-table">
        <div class="ld-row ld-row--head">
          <div class="ld-col ld-col--name">{{ t('scheme.strategy.groupName') }}</div>
          <div class="ld-col ld-col--zones">{{ t('scheme.strategy.colZones') }}</div>
          <div class="ld-col ld-col--subs">{{ t('scheme.strategy.colSubsystems') }}</div>
          <div class="ld-col ld-col--mode">{{ t('scheme.strategy.colMode') }}</div>
        </div>

        <div
          v-for="(group, gIdx) in modelValue.load_distribution.groups"
          :key="group.id"
          class="ld-row"
        >
          <!-- 分组名 -->
          <div class="ld-col ld-col--name">
            <div class="ld-name-row">
              <div class="ld-group-name">{{ t('scheme.strategy.groupName') }} {{ gIdx + 1 }}</div>
              <el-button
                text
                type="danger"
                :icon="Delete"
                :disabled="modelValue.load_distribution.groups.length <= 1"
                @click="removeGroup(group.id)"
              />
            </div>
            <div class="ld-stats">
              <div v-for="stat in groupStats.filter((item) => item.group_id === group.id)" :key="stat.group_id" class="ld-stats-list">
                <div class="ld-stat-line">
                  <span class="ld-stat-label">{{ t('scheme.strategy.coolingLoad') }}</span>
                  <span class="ld-stat-value">{{ stat.cooling_load_est.toFixed(1) }} <em>kW</em></span>
                </div>
                <div class="ld-stat-line">
                  <span class="ld-stat-label">{{ t('scheme.strategy.heatingLoad') }}</span>
                  <span class="ld-stat-value">{{ stat.heating_load_est.toFixed(1) }} <em>kW</em></span>
                </div>
                <div class="ld-stat-line">
                  <span class="ld-stat-label">{{ t('scheme.strategy.coolingCapacity') }}</span>
                  <span class="ld-stat-value">{{ stat.cooling_capacity_total.toFixed(1) }} <em>kW</em></span>
                </div>
                <div class="ld-stat-line">
                  <span class="ld-stat-label">{{ t('scheme.strategy.heatingCapacity') }}</span>
                  <span class="ld-stat-value">{{ stat.heating_capacity_total.toFixed(1) }} <em>kW</em></span>
                </div>
              </div>
            </div>
          </div>

          <!-- 负荷分区 tag -->
          <div class="ld-col ld-col--zones">
            <div class="ld-tag-wrap">
              <el-tag
                v-for="key in assignedZoneKeys(group.id)"
                :key="key"
                type="info"
                effect="plain"
                class="ld-tag ld-tag--fixed"
                :title="zoneInfo(key)?.name || key"
              >{{ zoneInfo(key)?.name || key }}</el-tag>
              <el-popover
                v-if="unassignedZoneOptions(group.id).length"
                placement="bottom-start"
                trigger="click"
                :width="280"
                @show="resetPicker(group.id, 'zone')"
              >
                <template #reference>
                  <el-button size="small" :icon="Plus" plain class="ld-add-btn">{{ t('scheme.strategy.addZone') }}</el-button>
                </template>
                <div class="ld-picker">
                  <div class="ld-picker-head">
                    <el-input
                      v-model="pickerSearch[pickerKey(group.id, 'zone')]"
                      size="small"
                      :placeholder="t('scheme.strategy.searchZone')"
                      clearable
                    />
                    <el-button size="small" link type="primary" @click="selectAllZones(group.id)">{{ t('scheme.strategy.selectAll') }}</el-button>
                  </div>
                  <div class="ld-picker-body">
                    <el-checkbox-group v-model="pickerSelected[pickerKey(group.id, 'zone')]">
                      <el-checkbox
                        v-for="zone in filteredZoneOptions(group.id)"
                        :key="zone.key"
                        :value="zone.key"
                        class="ld-picker-item"
                      >
                        <span class="ld-picker-name">{{ zone.name }}</span>
                        <span class="ld-meta">{{ zone.area.toFixed(1) }}㎡</span>
                      </el-checkbox>
                      <div v-if="!filteredZoneOptions(group.id).length" class="ld-picker-empty">{{ t('scheme.strategy.noMatch') }}</div>
                    </el-checkbox-group>
                  </div>
                  <div class="ld-picker-foot">
                    <span class="ld-meta">{{ t('scheme.strategy.selectedCount', { n: (pickerSelected[pickerKey(group.id, 'zone')] || []).length }) }}</span>
                    <el-button
                      size="small"
                      type="primary"
                      :disabled="!(pickerSelected[pickerKey(group.id, 'zone')] || []).length"
                      @click="confirmAddZones(group.id)"
                    >{{ t('scheme.strategy.add') }}</el-button>
                  </div>
                </div>
              </el-popover>
              <span v-if="!assignedZoneKeys(group.id).length && !unassignedZoneOptions(group.id).length" class="ld-empty">{{ t('scheme.strategy.noZones') }}</span>
            </div>
          </div>

          <!-- 系统 tag（竖向堆叠） -->
          <div class="ld-col ld-col--subs">
            <div class="ld-tag-wrap ld-tag-wrap--vertical">
              <el-tag
                v-for="sid in assignedSubsystemIds(group.id)"
                :key="sid"
                type="primary"
                effect="plain"
                class="ld-tag ld-tag--block"
                :title="subInfo(sid)?.name || sid"
              >{{ subInfo(sid)?.name || sid.slice(0, 8) }}</el-tag>
              <el-popover
                v-if="unassignedSubsystemOptions(group.id).length"
                placement="bottom-start"
                trigger="click"
                :width="280"
                @show="resetPicker(group.id, 'sub')"
              >
                <template #reference>
                  <el-button size="small" :icon="Plus" plain class="ld-add-btn ld-add-btn--block">{{ t('scheme.strategy.addSubsystem') }}</el-button>
                </template>
                <div class="ld-picker">
                  <div class="ld-picker-head">
                    <el-input
                      v-model="pickerSearch[pickerKey(group.id, 'sub')]"
                      size="small"
                      :placeholder="t('scheme.strategy.searchSubsystem')"
                      clearable
                    />
                    <el-button size="small" link type="primary" @click="selectAllSubsystems(group.id)">{{ t('scheme.strategy.selectAll') }}</el-button>
                  </div>
                  <div class="ld-picker-body">
                    <el-checkbox-group v-model="pickerSelected[pickerKey(group.id, 'sub')]">
                      <el-checkbox
                        v-for="sub in filteredSubsystemOptions(group.id)"
                        :key="sub.id"
                        :value="sub.id"
                        class="ld-picker-item"
                      >
                        <span class="ld-picker-name">{{ sub.name }}</span>
                        <span class="ld-meta">{{ t('scheme.types.' + sub.subsystem_type) }}</span>
                      </el-checkbox>
                      <div v-if="!filteredSubsystemOptions(group.id).length" class="ld-picker-empty">{{ t('scheme.strategy.noMatch') }}</div>
                    </el-checkbox-group>
                  </div>
                  <div class="ld-picker-foot">
                    <span class="ld-meta">{{ t('scheme.strategy.selectedCount', { n: (pickerSelected[pickerKey(group.id, 'sub')] || []).length }) }}</span>
                    <el-button
                      size="small"
                      type="primary"
                      :disabled="!(pickerSelected[pickerKey(group.id, 'sub')] || []).length"
                      @click="confirmAddSubsystems(group.id)"
                    >{{ t('scheme.strategy.add') }}</el-button>
                  </div>
                </div>
              </el-popover>
              <span v-if="!assignedSubsystemIds(group.id).length && !unassignedSubsystemOptions(group.id).length" class="ld-empty">{{ t('scheme.strategy.noSubsystems') }}</span>
            </div>
          </div>

          <!-- 分配方式 -->
          <div class="ld-col ld-col--mode">
            <el-radio-group
              :model-value="groupModeOf(group.id)"
              size="small"
              @update:model-value="(val) => updateGroupMode(group.id, val)"
            >
              <el-radio value="fixed_ratio">{{ t('scheme.strategy.fixedRatio') }}</el-radio>
              <el-radio value="by_priority">{{ t('scheme.strategy.byPriority') }}</el-radio>
            </el-radio-group>

            <div
              v-if="assignedSubsystemIds(group.id).length && groupModeOf(group.id) === 'fixed_ratio'"
              class="ld-mode-body"
            >
              <div v-for="sid in assignedSubsystemIds(group.id)" :key="sid" class="ld-ratio-row">
                <span class="ld-ratio-name" :title="subInfo(sid)?.name || sid">{{ subInfo(sid)?.name || sid.slice(0, 8) }}</span>
                <el-input-number
                  :model-value="modelValue.load_distribution.group_settings[group.id]?.ratios?.[sid] || 0"
                  :min="0"
                  :max="100"
                  :step="1"
                  :precision="1"
                  size="small"
                  controls-position="right"
                  @update:model-value="(val) => updateRatio(group.id, sid, Number(val || 0))"
                />
                <span class="ld-ratio-unit">%</span>
              </div>
              <div class="ld-ratio-total">
                {{ t('scheme.strategy.total') }} {{ assignedSubsystemIds(group.id).reduce((acc, sid) => acc + Number(modelValue.load_distribution.group_settings[group.id]?.ratios?.[sid] || 0), 0).toFixed(1) }}%
              </div>
            </div>

            <div
              v-else-if="assignedSubsystemIds(group.id).length && groupModeOf(group.id) === 'by_priority'"
              class="ld-mode-body ld-priority-chain"
            >
              <div class="ld-priority-hint">{{ t('scheme.strategy.dragHint') }}</div>
              <draggable
                :model-value="sortedPriorityIds(group.id)"
                :item-key="itemKeyOfSid"
                handle=".ld-priority-tag"
                ghost-class="ld-priority-tag--ghost"
                chosen-class="ld-priority-tag--chosen"
                drag-class="ld-priority-tag--drag"
                animation="180"
                class="ld-priority-list"
                @end="(evt) => reorderPriorityByIndex(group.id, evt.oldIndex ?? -1, evt.newIndex ?? -1)"
              >
                <template #item="{ element: sid, index: idx }">
                  <div
                    class="ld-priority-tag"
                    :title="subInfo(sid)?.name || sid"
                  >
                    <span class="ld-priority-idx">{{ idx + 1 }}</span>
                    <span class="ld-priority-name">{{ subInfo(sid)?.name || sid.slice(0, 8) }}</span>
                  </div>
                </template>
              </draggable>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="strategy-card" shadow="never">
      <template #header>
        <div class="card-title">{{ t('scheme.strategy.subsystemDetailsTitle') }}</div>
      </template>

      <el-collapse v-model="activeStrategySubs" @change="onStrategyCollapseChange">
        <el-collapse-item v-for="sub in subsystems" :key="sub.id || sub.subsystem_index" :name="sub.id || sub.subsystem_index">
          <template #title>
            <div class="sub-title-row">
              <span>{{ sub.name }}</span>
              <el-tag size="small" type="info" effect="plain">{{ t('scheme.types.' + sub.subsystem_type) }}</el-tag>
              <el-button
                size="small"
                :icon="RefreshRight"
                class="sub-title-reset"
                @click.stop="resetSubsystemStrategy(sub)"
              >{{ t('scheme.strategy.resetSubsystemDefault') }}</el-button>
            </div>
          </template>

          <!-- 重型内容仅在该子系统首次展开后挂载，且持久保留 -->
          <template v-if="isStrategySubMounted(sub)">
          <el-alert
            v-for="(issue, idx) in subsystemGeneralIssues(sub.id)"
            :key="`${sub.id}-gen-${idx}`"
            :type="issue.severity === 'error' ? 'error' : 'warning'"
            :title="issue.message"
            show-icon
            :closable="false"
            class="strategy-alert"
          />

          <template v-if="getSubsystemStrategy(sub)">
            <div class="sub-section">
              <div class="sub-section-head">
                <div class="sub-section-title">{{ t('scheme.strategy.tabSchedule') }}</div>
                <el-button size="small" plain :icon="Plus" @click="addSchedule(sub)">{{ t('scheme.strategy.addSchedule') }}</el-button>
              </div>
              <el-alert
                v-for="(issue, idx) in subsystemScheduleIssues(sub.id)"
                :key="`${sub.id}-sch-${idx}`"
                :type="issue.severity === 'error' ? 'error' : 'warning'"
                :title="issue.message"
                show-icon
                :closable="false"
                class="strategy-alert"
              />
              <div class="schedule-stack">
                <ScheduleEditor
                  v-for="(schedule, idx) in getSubsystemStrategy(sub)?.run_schedules || []"
                  :key="`${sub.id}-${idx}`"
                  :model-value="schedule"
                  :index="idx"
                  mode="binary"
                  :conflict-message="scheduleConflictMessage(getSubsystemStrategy(sub)?.run_schedules || [], idx)"
                  :removable="(getSubsystemStrategy(sub)?.run_schedules?.length || 0) > 1"
                  @update:model-value="(val) => updateSchedule(sub, idx, val)"
                  @remove="removeSchedule(sub, idx)"
                />
              </div>
            </div>

            <div class="sub-section">
              <div class="sub-section-title">{{ t('scheme.strategy.tabWaterTemp') }}</div>
              <el-alert
                v-for="(issue, idx) in subsystemWaterTempIssues(sub.id)"
                :key="`${sub.id}-wt-${idx}`"
                :type="issue.severity === 'error' ? 'error' : 'warning'"
                :title="issue.message"
                show-icon
                :closable="false"
                class="strategy-alert"
              />
              <div class="profile-stack" v-if="getSubsystemStrategy(sub)?.subsystem_type === 'chiller_plant'">
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.chw_supply"
                  :label="t('scheme.strategy.chwSupply')"
                  :min="1"
                  :max="25"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'chiller_plant') next.water_temp.chw_supply = val })"
                />
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.chw_delta"
                  :label="t('scheme.strategy.chwDelta')"
                  :min="1"
                  :max="15"
                  :allow-constant-pressure="true"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'chiller_plant') next.water_temp.chw_delta = val })"
                />
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.approach"
                  :label="t('scheme.strategy.approach')"
                  :min="1"
                  :max="15"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'chiller_plant') next.water_temp.approach = val })"
                />
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.cw_delta"
                  :label="t('scheme.strategy.cwDelta')"
                  :min="1"
                  :max="15"
                  :allow-constant-pressure="true"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'chiller_plant') next.water_temp.cw_delta = val })"
                />
              </div>
              <div class="profile-stack" v-else-if="getSubsystemStrategy(sub)?.subsystem_type === 'air_cooled'">
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.cooling_supply"
                  :label="t('scheme.strategy.coolingSupply')"
                  :min="1"
                  :max="25"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'air_cooled') next.water_temp.cooling_supply = val })"
                />
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.cooling_delta"
                  :label="t('scheme.strategy.coolingDelta')"
                  :min="1"
                  :max="15"
                  :allow-constant-pressure="true"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'air_cooled') next.water_temp.cooling_delta = val })"
                />
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.heating_supply"
                  :label="t('scheme.strategy.heatingSupply')"
                  :min="30"
                  :max="100"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'air_cooled') next.water_temp.heating_supply = val })"
                />
                <StrategyValueProfileEditor
                  :model-value="getSubsystemStrategy(sub)?.water_temp.heating_delta"
                  :label="t('scheme.strategy.heatingDelta')"
                  :min="1"
                  :max="15"
                  :allow-constant-pressure="true"
                  @update:model-value="(val) => updateSubsystemStrategy(sub, (next) => { if (next.subsystem_type === 'air_cooled') next.water_temp.heating_delta = val })"
                />
              </div>
              <el-empty v-else :image-size="80" :description="t('scheme.strategy.sharedTowerTba')" />
            </div>

            <div class="sub-section" v-if="getSubsystemStrategy(sub)?.subsystem_type === 'chiller_plant' || getSubsystemStrategy(sub)?.subsystem_type === 'air_cooled'">
              <div class="sub-section-head">
                <div class="sub-section-title">{{ t('scheme.strategy.tabEquipment') }}</div>
                <div class="card-actions">
                  <el-button size="small" :icon="RefreshRight" @click="resetSubsystemStrategy(sub)">{{ t('scheme.strategy.autoGenerate') }}</el-button>
                  <el-button size="small" plain :icon="Plus" @click="addStage(sub)">{{ t('scheme.strategy.addStaging') }}</el-button>
                </div>
              </div>

              <!-- Stage table (chiller_plant) -->
              <div class="equip-block" v-if="getSubsystemStrategy(sub)?.subsystem_type === 'chiller_plant'">
                <div class="equip-block-title">加减机策略表</div>
                <el-alert
                  v-for="(issue, idx) in subsystemStageIssues(sub.id)"
                  :key="`${sub.id}-stage-${idx}`"
                  :type="issue.severity === 'error' ? 'error' : 'warning'"
                  :title="issue.message"
                  show-icon
                  :closable="false"
                  class="strategy-alert"
                />
                <div class="stage-table">
                <table class="st-table">
                  <thead>
                    <tr>
                      <th class="st-stage-col">档位</th>
                      <th v-for="combo in sub.combos" :key="combo.id || combo.combo_index" class="st-combo-col">
                        <div class="st-combo-head">
                          <div class="st-combo-name">{{ comboModelName(sub.id, combo.id) || t('scheme.strategy.comboTitle', { n: combo.combo_index }) }}</div>
                          <div class="st-combo-sub">{{ comboCapacitySub(sub.id, combo.id) }}</div>
                        </div>
                      </th>
                      <th class="st-num-col">{{ t('scheme.strategy.loadingDown') }}</th>
                      <th class="st-num-col">{{ t('scheme.strategy.loadingUp') }}</th>
                      <th class="st-cap-col">{{ t('scheme.strategy.capacitySegment') }}</th>
                      <th class="st-act-col"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(stage, stageIdx) in getSubsystemStrategy(sub)?.equipment.chiller_stages || []" :key="stage.id">
                      <td class="st-stage-col">{{ stageIdx + 1 }}</td>
                      <td v-for="combo in sub.combos" :key="combo.id || combo.combo_index" :class="{ 'is-zero': !(combo.id && stage.combo_counts[combo.id]) }">
                        <el-input-number
                          :model-value="combo.id ? stage.combo_counts[combo.id] || 0 : 0"
                          :min="0"
                          :max="combo.primary_count"
                          :step="1"
                          size="small"
                          controls-position="right"
                          @update:model-value="(val) => combo.id && updateStageCount(sub, stageIdx, combo.id, Number(val || 0))"
                        />
                      </td>
                      <td>
                        <el-input-number
                          :model-value="stage.loading_down || undefined"
                          :min="30" :max="100" size="small" controls-position="right"
                          :disabled="stageIdx === 0"
                          @update:model-value="(val) => updateStageField(sub, stageIdx, 'loading_down', Number(val || 0))"
                        />
                      </td>
                      <td>
                        <el-input-number
                          :model-value="stage.loading_up || undefined"
                          :min="30" :max="100" size="small" controls-position="right"
                          :disabled="stageIdx === (getSubsystemStrategy(sub)?.equipment.chiller_stages.length || 1) - 1"
                          @update:model-value="(val) => updateStageField(sub, stageIdx, 'loading_up', Number(val || 0))"
                        />
                      </td>
                      <td class="st-cap-col">{{ stage.cooling_capacity_min ?? '-' }} ~ {{ stage.cooling_capacity_max ?? '-' }}</td>
                      <td class="st-act-col">
                        <el-button text :icon="Plus" @click="insertStageAt(sub, stageIdx)" :title="'在此行下方插入新档位'" />
                        <el-button text type="danger" :icon="Delete"
                          :disabled="(getSubsystemStrategy(sub)?.equipment.chiller_stages?.length || 0) <= 1"
                          @click="removeStage(sub, stageIdx)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                </div>
              </div>

              <!-- Stage table (air_cooled) -->
              <div class="equip-block" v-else-if="getSubsystemStrategy(sub)?.subsystem_type === 'air_cooled'">
                <div class="equip-block-title">加减机策略表</div>
                <el-alert
                  v-for="(issue, idx) in subsystemStageIssues(sub.id)"
                  :key="`${sub.id}-stage-ac-${idx}`"
                  :type="issue.severity === 'error' ? 'error' : 'warning'"
                  :title="issue.message"
                  show-icon
                  :closable="false"
                  class="strategy-alert"
                />
                <div class="stage-table">
                <table class="st-table">
                  <thead>
                    <tr>
                      <th class="st-stage-col">档位</th>
                      <th v-for="combo in sub.combos" :key="combo.id || combo.combo_index" class="st-combo-col">
                        <div class="st-combo-head">
                          <div class="st-combo-name">{{ t('scheme.strategy.comboTitle', { n: combo.combo_index }) }}</div>
                          <div class="st-combo-sub">{{ derivedComboLabel(sub.id, combo.id) }}</div>
                        </div>
                      </th>
                      <th class="st-num-col">{{ t('scheme.strategy.loadingDown') }}</th>
                      <th class="st-num-col">{{ t('scheme.strategy.loadingUp') }}</th>
                      <th class="st-cap-col">{{ t('scheme.strategy.capSegmentCool') }} / {{ t('scheme.strategy.capSegmentHeat') }}</th>
                      <th class="st-act-col"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(stage, stageIdx) in getSubsystemStrategy(sub)?.equipment.module_stages || []" :key="stage.id">
                      <td class="st-stage-col">{{ stageIdx + 1 }}</td>
                      <td v-for="combo in sub.combos" :key="combo.id || combo.combo_index" :class="{ 'is-zero': !(combo.id && stage.combo_counts[combo.id]) }">
                        <el-input-number
                          :model-value="combo.id ? stage.combo_counts[combo.id] || 0 : 0"
                          :min="0"
                          :max="combo.group_count"
                          :step="1"
                          size="small"
                          controls-position="right"
                          @update:model-value="(val) => combo.id && updateStageCount(sub, stageIdx, combo.id, Number(val || 0))"
                        />
                      </td>
                      <td>
                        <el-input-number
                          :model-value="stage.loading_down || undefined"
                          :min="0" :max="100" size="small" controls-position="right"
                          :disabled="stageIdx === 0"
                          @update:model-value="(val) => updateStageField(sub, stageIdx, 'loading_down', Number(val || 0))"
                        />
                      </td>
                      <td>
                        <el-input-number
                          :model-value="stage.loading_up || undefined"
                          :min="0" :max="100" size="small" controls-position="right"
                          :disabled="stageIdx === (getSubsystemStrategy(sub)?.equipment.module_stages.length || 1) - 1"
                          @update:model-value="(val) => updateStageField(sub, stageIdx, 'loading_up', Number(val || 0))"
                        />
                      </td>
                      <td class="st-cap-col">
                        <div>{{ stage.cooling_capacity_min ?? '-' }} ~ {{ stage.cooling_capacity_max ?? '-' }}</div>
                        <div class="st-cap-heat">{{ stage.heating_capacity_min ?? '-' }} ~ {{ stage.heating_capacity_max ?? '-' }}</div>
                      </td>
                      <td class="st-act-col">
                        <el-button text :icon="Plus" @click="insertStageAt(sub, stageIdx)" :title="'在此行下方插入新档位'" />
                        <el-button text type="danger" :icon="Delete"
                          :disabled="(getSubsystemStrategy(sub)?.equipment.module_stages?.length || 0) <= 1"
                          @click="removeStage(sub, stageIdx)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                </div>
              </div>

              <div class="equip-block">
                <div class="equip-block-title">水泵 / 冷却塔控制</div>
                <el-alert
                  v-for="(issue, idx) in subsystemPumpIssues(sub.id)"
                  :key="`${sub.id}-pump-${idx}`"
                  :type="issue.severity === 'error' ? 'error' : 'warning'"
                  :title="issue.message"
                  show-icon
                  :closable="false"
                  class="strategy-alert"
                />
                <div class="pump-grid">
                <template v-if="getSubsystemStrategy(sub)?.subsystem_type === 'chiller_plant'">
                  <div class="pump-card">
                    <table class="pump-table">
                      <thead>
                        <tr>
                          <th class="pt-name"></th>
                          <th>最小频率(Hz)</th>
                          <th>最大频率(Hz)</th>
                          <th class="pt-extra">m</th>
                          <th class="pt-extra">k</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td class="pt-name">{{ t('scheme.strategy.chwPump') }}</td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.chw_pump.min_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'chw_pump', 'min_freq', Number(val || 0))" /></td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.chw_pump.max_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'chw_pump', 'max_freq', Number(val || 0))" /></td>
                          <td class="pt-extra"></td>
                          <td class="pt-extra"></td>
                        </tr>
                        <tr>
                          <td class="pt-name">{{ t('scheme.strategy.cwPump') }}</td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.cw_pump.min_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'cw_pump', 'min_freq', Number(val || 0))" /></td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.cw_pump.max_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'cw_pump', 'max_freq', Number(val || 0))" /></td>
                          <td class="pt-extra"></td>
                          <td class="pt-extra"></td>
                        </tr>
                        <tr>
                          <td class="pt-name">{{ t('scheme.strategy.tower') }}</td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.tower.min_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'tower', 'min_freq', Number(val || 0))" /></td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.tower.max_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'tower', 'max_freq', Number(val || 0))" /></td>
                          <td class="pt-extra"><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.tower.m" :min="1" :max="5" @update:model-value="(val) => updateEquipmentField(sub, 'tower', 'm', Number(val || 1))" /></td>
                          <td class="pt-extra"><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.tower.k" :min="0" :max="20" @update:model-value="(val) => updateEquipmentField(sub, 'tower', 'k', Number(val || 0))" /></td>
                        </tr>
                      </tbody>
                    </table>
                    <div class="pump-foot-hint">m、k 为系数，n 为制冷机开启台数，设备开启台数 = m·n + k</div>
                  </div>
                </template>

                <template v-else-if="getSubsystemStrategy(sub)?.subsystem_type === 'air_cooled'">
                  <div class="pump-card" v-if="getSubsystemStrategy(sub)?.equipment.pump || getSubsystemStrategy(sub)?.equipment.chw_pump || getSubsystemStrategy(sub)?.equipment.hw_pump">
                    <table class="pump-table">
                      <thead>
                        <tr>
                          <th class="pt-name"></th>
                          <th>最小频率(Hz)</th>
                          <th>最大频率(Hz)</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-if="getSubsystemStrategy(sub)?.equipment.pump">
                          <td class="pt-name">{{ t('scheme.strategy.pump') }}</td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.pump?.min_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'pump', 'min_freq', Number(val || 0))" /></td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.pump?.max_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'pump', 'max_freq', Number(val || 0))" /></td>
                        </tr>
                        <tr v-if="getSubsystemStrategy(sub)?.equipment.chw_pump">
                          <td class="pt-name">{{ t('scheme.strategy.chwPumpAlt') }}</td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.chw_pump?.min_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'chw_pump', 'min_freq', Number(val || 0))" /></td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.chw_pump?.max_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'chw_pump', 'max_freq', Number(val || 0))" /></td>
                        </tr>
                        <tr v-if="getSubsystemStrategy(sub)?.equipment.hw_pump">
                          <td class="pt-name">{{ t('scheme.strategy.hwPumpAlt') }}</td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.hw_pump?.min_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'hw_pump', 'min_freq', Number(val || 0))" /></td>
                          <td><el-input-number size="small" controls-position="right" :model-value="getSubsystemStrategy(sub)?.equipment.hw_pump?.max_freq" :min="1" :max="50" @update:model-value="(val) => updateEquipmentField(sub, 'hw_pump', 'max_freq', Number(val || 0))" /></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
                </div>
              </div>
            </div>
          </template>
          </template>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<style scoped>
.strategy-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.strategy-card {
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
}
.card-title {
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.card-head,
.sub-section-head,
.group-head,
.stage-head,
.sub-actions,
.margin-row,
.mode-row,
.pump-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.card-actions {
  display: flex;
  gap: 8px;
}
.margin-desc {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.safety-margin-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 4px 0 8px;
}
.safety-margin-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
}
.safety-margin-bar :deep(.el-input-number) {
  width: 130px;
}
.group-grid,
.assign-grid,
.profile-stack,
.stage-stack,
.schedule-stack {
  display: grid;
  gap: 12px;
}
.group-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  margin-top: 12px;
}
.group-card,
.assign-card,
.stage-card,
.pump-card {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 12px;
  background: #fff;
}
.group-stats {
  margin-top: 10px;
}
.group-stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  font-size: var(--font-size-sm);
  color: var(--color-neutral-700);
}
.group-setting-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-subtle);
}
.group-setting-title,
.assign-title,
.sub-section-title,
.pump-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: 8px;
}
.sub-section-title {
  font-size: var(--font-size-base);
  padding-left: 10px;
  border-left: 3px solid #3b82f6;
  line-height: 1.2;
}
.equip-block {
  margin-top: 14px;
}
.equip-block-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-600);
  margin-bottom: 6px;
  padding-left: 8px;
  border-left: 2px solid var(--border-base);
}
.pump-foot-hint {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: left;
}
.pump-hint {
  font-size: 11px;
  font-weight: var(--font-weight-regular);
  color: var(--text-muted);
  margin-left: 8px;
}
.group-setting-row,
.assign-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}
.group-total {
  margin-top: 8px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.assign-grid {
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  margin-top: 14px;
}
.assign-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.assign-meta {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.sub-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.sub-title-reset {
  margin-left: auto;
}
.sub-section {
  margin-top: 16px;
}
.sub-actions {
  margin-bottom: 10px;
}
.stage-combo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 10px;
}
/* ===== compact stage table (replaces stacked stage cards) ===== */
.stage-table {
  margin-top: 10px;
  overflow-x: auto;
  overflow-y: auto;
  max-height: 420px; /* 约 10 行： 36px 行高 × 10 + 表头 */
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.st-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
}
.st-table tbody td.is-zero :deep(.el-input-number .el-input__inner) {
  color: var(--border-base);
}
.st-table tbody td.is-zero :deep(.el-input-number .el-input__wrapper) {
  background: var(--color-neutral-50);
  box-shadow: 0 0 0 1px var(--color-neutral-100) inset;
}
/* 选中时恢复正常样式以区别于禁用输入 */
.st-table tbody td.is-zero:focus-within :deep(.el-input-number .el-input__inner) {
  color: var(--text-body);
}
.st-table tbody td.is-zero:focus-within :deep(.el-input-number .el-input__wrapper) {
  background: #ffffff;
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff) inset;
}
.st-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  color: var(--text-body);
}
.st-table thead th {
  background: var(--color-neutral-100);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  padding: 8px 10px;
  text-align: center;
  border-bottom: 1px solid var(--border-subtle);
  white-space: nowrap;
}
.st-table tbody td {
  padding: 2px 5px;
  text-align: center;
  border-bottom: 1px solid var(--color-neutral-100);
  vertical-align: middle;
}
.st-table tbody tr:last-child td {
  border-bottom: 0;
}
.st-table tbody tr:hover {
  background: var(--color-neutral-50);
}
.st-stage-col {
  width: 56px;
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-600);
  background: var(--color-neutral-50);
}
.st-num-col, .st-cap-col {
  min-width: 110px;
}
.st-act-col {
  width: 72px;
  white-space: nowrap;
}
.st-act-col :deep(.el-button) {
  padding: 4px;
  margin: 0 1px;
}
.st-combo-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: center;
}
.st-combo-name {
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.st-combo-sub {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: var(--font-weight-regular);
}
.st-cap-heat {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.st-table :deep(.el-input-number) {
  width: 84px !important;
}
.st-table :deep(.el-input-number .el-input__wrapper) {
  padding-left: 4px;
  padding-right: 4px;
}
.st-table :deep(.el-input-number .el-input__inner) {
  text-align: center;
}
.stage-combo-cell {
  padding: 8px;
  border-radius: var(--radius-md);
  background: var(--color-neutral-50);
  border: 1px solid var(--border-subtle);
}
.stage-label {
  font-size: var(--font-size-xs);
  color: var(--color-neutral-600);
  margin-bottom: 6px;
}
.stage-range-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.stage-range-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stage-capacity {
  display: flex;
  align-items: center;
  font-size: var(--font-size-xs);
  color: var(--color-neutral-600);
}
.pump-grid {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}
.pump-row {
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
}
/* compact pump table */
.pump-table {
  width: auto;
  border-collapse: collapse;
  margin-top: 8px;
  font-size: var(--font-size-sm);
}
.pump-table thead th {
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  padding: 4px 10px;
  text-align: center;
  font-size: var(--font-size-xs);
}
.pump-table tbody td {
  padding: 4px 10px;
  text-align: center;
  vertical-align: middle;
}
.pump-table .pt-name {
  text-align: left;
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  width: 96px;
}
.pump-table .pt-extra {
  width: 96px;
  color: var(--text-muted);
}
.pump-table :deep(.el-input-number) {
  width: 96px !important;
}
.pump-table :deep(.el-input-number .el-input__wrapper) {
  padding-left: 4px;
  padding-right: 4px;
}
.pump-table :deep(.el-input-number .el-input__inner) {
  text-align: center;
}
.strategy-alert {
  margin-bottom: 10px;
}
@media (max-width: 900px) {
  .stage-range-row,
  .group-stat-grid {
    grid-template-columns: 1fr;
  }
  .group-setting-row,
  .assign-row {
    grid-template-columns: 1fr;
  }
}

/* ===== Load distribution table (matches design ref 1.png) ===== */
.ld-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ld-count-label {
  width: 30px;
  min-width: 30px;;
  font-size: var(--font-size-sm);
  color: var(--color-neutral-600);
}
/* picker popover */
.ld-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ld-picker-head {
  display: flex;
  gap: 6px;
  align-items: center;
}
.ld-picker-body {
  max-height: 220px;
  overflow-y: auto;
  padding: 4px 2px;
  border-top: 1px solid var(--color-neutral-100);
  border-bottom: 1px solid var(--color-neutral-100);
}
.ld-picker-body :deep(.el-checkbox) {
  display: flex;
  align-items: center;
  width: 100%;
  margin-right: 0;
  padding: 4px 6px;
  border-radius: var(--radius-xs);
  height: auto;
}
.ld-picker-body :deep(.el-checkbox:hover) {
  background: var(--color-neutral-100);
}
.ld-picker-body :deep(.el-checkbox__label) {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ld-picker-name {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.ld-picker-empty {
  padding: 12px;
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
.ld-picker-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ld-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: transparent;
  border: 0;
}
.ld-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) minmax(150px, 0.25fr) minmax(240px, 0.28fr);
  gap: 0;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: #fff;
  overflow: hidden;
}
.ld-row:first-child {
  border-top: 1px solid var(--border-subtle);
}
.ld-row--head {
  background: var(--color-neutral-100);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  border-color: transparent;
}
.ld-row--head .ld-col {
  padding: 8px 14px;
}
.ld-col {
  padding: 12px 14px;
  border-left: 1px solid var(--color-neutral-100);
  min-width: 0;
}
.ld-col:first-child {
  border-left: 0;
  background: var(--color-neutral-50);
}
.ld-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ld-stats {
  margin-top: 10px;
}
.ld-stats-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ld-stat-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  font-size: var(--font-size-xs);
  line-height: 1.6;
}
.ld-stat-label {
  color: var(--text-muted);
  white-space: nowrap;
}
.ld-stat-value {
  color: var(--text-body);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.ld-stat-value em {
  font-style: normal;
  font-weight: var(--font-weight-regular);
  color: var(--text-muted);
  font-size: 11px;
  margin-left: 2px;
}
.ld-tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}
.ld-tag-wrap--vertical {
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: stretch;
  gap: 4px;
}
.ld-tag--block {
  width: 100%;
  max-width: 100%;
  display: flex;
  align-items: center;
  font-size: var(--font-size-xs);
}
.ld-tag--block :deep(.el-tag__content) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ld-add-btn--block {
  width: 100%;
  justify-content: center;
}
.ld-tag {
  border-radius: var(--radius-sm);
  max-width: 140px;
}
.ld-tag :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ld-tag--fixed {
  width: 75px;
  max-width: 75px;
  padding: 0 4px;
  font-size: var(--font-size-xs);
}
.ld-tag--fixed :deep(.el-tag__content) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ld-tag--fixed :deep(.el-icon.el-tag__close) {
  margin-left: 2px;
  flex-shrink: 0;
}
.ld-group-name {
  flex: 1;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  padding: 4px 0;
}
.ld-add-btn {
  border-style: dashed;
}
.ld-empty {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
.ld-meta {
  margin-left: 6px;
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}
.ld-mode-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-subtle);
}
.ld-ratio-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px 14px;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
  font-size: var(--font-size-xs);
}
.ld-ratio-name {
  color: var(--color-neutral-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.ld-ratio-unit {
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}
.ld-ratio-total {
  margin-top: 4px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  text-align: right;
}
.ld-priority-chain {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}
.ld-priority-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ld-priority-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 2px;
}
.ld-priority-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: var(--brand-primary-soft);
  color: var(--text-body);
  font-size: var(--font-size-xs);
  border: 1px solid var(--brand-primary-soft);
  cursor: grab;
  user-select: none;
  transition: background 0.15s, box-shadow 0.15s;
}
.ld-priority-tag:hover {
  background: var(--brand-primary-soft);
}
.ld-priority-tag:active {
  cursor: grabbing;
}
.ld-priority-tag--ghost {
  opacity: 0.4;
  background: var(--brand-primary-soft);
}
.ld-priority-tag--chosen {
  box-shadow: 0 0 0 2px var(--brand-primary);
}
.ld-priority-tag--drag {
  opacity: 0.9;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}
.ld-priority-actions {
  display: inline-flex;
  align-items: center;
  gap: 0;
  margin-left: 2px;
}
.ld-priority-btn {
  padding: 2px !important;
  height: 20px !important;
  min-height: 20px !important;
  color: var(--color-neutral-600) !important;
}
.ld-priority-btn:hover {
  color: var(--brand-primary-hover) !important;
  background: rgba(79, 70, 229, 0.08) !important;
}
.ld-priority-idx {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--brand-primary-hover);
  color: #fff;
  font-size: 11px;
  font-weight: var(--font-weight-bold);
}
.ld-priority-name {
  font-weight: var(--font-weight-semibold);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 900px) {
  .ld-row,
  .ld-row--head {
    grid-template-columns: 1fr;
  }
  .ld-row--head {
    display: none;
  }
  .ld-col {
    border-left: 0;
    border-top: 1px dashed var(--color-neutral-100);
  }
  .ld-col:first-child {
    border-top: 0;
  }
}
</style>
