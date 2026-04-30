<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, triggerRef, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getBuilding, updateBuilding } from '@/api/buildings'
import { getSimulations } from '@/api/simulation'
import type { Building, BuildingUpdate, BuildingZone, ParamConfig, DaySchedule, ZonePosition, WallConfig } from '@/types/building'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, ArrowDown, CopyDocument, FolderAdd, ArrowLeft, FolderChecked, Setting } from '@element-plus/icons-vue'
import { ZONE_PRESETS, PRESET_KEYS } from '@/data/zone-presets'
import { useResponsive } from '@/composables/useResponsive'
import ScheduleEditor from '@/components/building/ScheduleEditor.vue'

const { isMobile } = useResponsive()

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const building = ref<Building | null>(null)
const saving = ref(false)
const selectedZoneIdx = ref(0)
const activePresetKey = ref('')

watch(selectedZoneIdx, () => { activePresetKey.value = '' })

// Edit state
const editType = ref('')
const editClimateZone = ref('')
const editZones = ref<BuildingZone[]>([])

const projectId = route.params.projectId as string
const buildingId = route.params.buildingId as string

// Param config metadata for rendering
interface ParamMeta {
  key: string; label: string; min: number; max: number; precision: number; step: number
}
const PARAM_METAS: ParamMeta[] = [
  { key: 'people_density', label: 'building.internalGains.people', min: 0, max: 1, precision: 3, step: 0.01 },
  { key: 'lighting_density', label: 'building.internalGains.lighting', min: 0, max: 50, precision: 1, step: 1 },
  { key: 'equipment_density', label: 'building.internalGains.equipment', min: 0, max: 50, precision: 1, step: 1 },
  { key: 'fresh_air_volume', label: 'building.internalGains.freshAir', min: 0, max: 200, precision: 1, step: 5 },
]
const SETPOINT_METAS: ParamMeta[] = [
  { key: 'temperature', label: 'building.setpoint.temperature', min: 10, max: 35, precision: 1, step: 0.5 },
  { key: 'relative_humidity', label: 'building.setpoint.humidity', min: 20, max: 90, precision: 0, step: 5 },
]

function getParam(zone: BuildingZone, key: string): ParamConfig {
  return (zone as any)[key] as ParamConfig
}

const PARAM_UNITS: Record<string, string> = {
  people_density: '人/m²',
  lighting_density: 'W/m²',
  equipment_density: 'W/m²',
  fresh_air_volume: 'm³/h·人',
  temperature: '℃',
  relative_humidity: '%',
}
function paramUnit(key: string): string {
  return PARAM_UNITS[key] || ''
}

const PARAM_TYPE_MAP: Record<string, 'people' | 'lighting' | 'equipment' | 'fresh'> = {
  people_density: 'people',
  lighting_density: 'lighting',
  equipment_density: 'equipment',
  fresh_air_volume: 'fresh',
}
function paramType(key: string): 'people' | 'lighting' | 'equipment' | 'fresh' | undefined {
  return PARAM_TYPE_MAP[key]
}

function createParamConfig(val: number): ParamConfig {
  return { mode: 'fixed', fixed_value: val, schedules: [] }
}

function createSchedule(value: number, name?: string, days?: number[], hours?: number[]): DaySchedule {
  return {
    name: name || '',
    start_month: 1, start_day: 1, end_month: 12, end_day: 31,
    days: days || [1, 2, 3, 4, 5, 6, 7],
    hours: hours || [8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    value,
  }
}

function createDefaultZone(name?: string): BuildingZone {
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
    people_density: deepCopyParam(preset.people_density),
    people_heat_gain: preset.people_heat_gain ?? 134,
    lighting_density: deepCopyParam(preset.lighting_density),
    equipment_density: deepCopyParam(preset.equipment_density),
    fresh_air_volume: deepCopyParam(preset.fresh_air_volume),
    temperature: preset.temperature ? deepCopyParam(preset.temperature) : createParamConfig(26),
    relative_humidity: preset.relative_humidity ? deepCopyParam(preset.relative_humidity) : createParamConfig(50),
  }
}

function deepCopyParam(src: ParamConfig): ParamConfig {
  return JSON.parse(JSON.stringify(src))
}

function applyPreset(presetKey: string) {
  const preset = ZONE_PRESETS[presetKey]
  if (!preset) return
  const z = activeZone.value
  if (!z) return
  z.name = t(`building.zone.presets.${presetKey}`)
  // Apply envelope
  z.floor_height = preset.floor_height
  z.wall_u_value = preset.wall_u_value
  z.window_u_value = preset.window_u_value
  z.window_wall_ratio = preset.window_wall_ratio
  z.roof_u_value = preset.roof_u_value
  // Apply full param configs (deep copy to avoid shared references)
  z.people_density = deepCopyParam(preset.people_density)
  z.people_heat_gain = preset.people_heat_gain ?? 134
  z.lighting_density = deepCopyParam(preset.lighting_density)
  z.equipment_density = deepCopyParam(preset.equipment_density)
  z.fresh_air_volume = deepCopyParam(preset.fresh_air_volume)
  // Apply setpoints if present in preset
  if (preset.temperature) z.temperature = deepCopyParam(preset.temperature)
  if (preset.relative_humidity) z.relative_humidity = deepCopyParam(preset.relative_humidity)
  // Track selected preset
  activePresetKey.value = presetKey
  markDirty()
  queueConflictCheck()
  ElMessage.success(`${t(`building.zone.presets.${presetKey}`)} ✓`)
}

// ----- Schedule helpers -----
const MAX_SCHEDULES = 20

/** Internal-gain param keys (for new bar-chart editor) */
const INTERNAL_GAIN_KEYS = ['people_density', 'lighting_density', 'equipment_density', 'fresh_air_volume']

/** Create a fully-on (24h @ 100%) schedule with hourly_ratios */
function createRatiosSchedule(name = ''): DaySchedule {
  return {
    name,
    start_month: 1, start_day: 1, end_month: 12, end_day: 31,
    days: [1, 2, 3, 4, 5, 6, 7],
    hours: Array.from({ length: 24 }, (_, i) => i),
    value: 0,
    hourly_ratios: new Array(24).fill(100),
  }
}

/** Create an office-pattern schedule (9-18 @ 100%) */
function createOfficeRatiosSchedule(name = ''): DaySchedule {
  const ratios = new Array(24).fill(0) as number[]
  for (let h = 9; h <= 18; h++) ratios[h] = 100
  ratios[8] = 50; ratios[19] = 30
  return {
    name,
    start_month: 1, start_day: 1, end_month: 12, end_day: 31,
    days: [1, 2, 3, 4, 5],
    hours: Array.from({ length: 24 }, (_, i) => i),
    value: 0,
    hourly_ratios: ratios,
  }
}

/** Ensure an internal-gain ParamConfig is in scheduled mode with at least 1 schedule */
function normalizeInternalGainParam(p: ParamConfig): void {
  if (!p) return
  // Force scheduled mode (no more 'fixed' for internal gains)
  p.mode = 'scheduled'
  if (!Array.isArray(p.schedules) || p.schedules.length === 0) {
    p.schedules = [createOfficeRatiosSchedule(t('building.schedule.presetWeekday'))]
  }
}

function addScheduleForParam(param: ParamConfig) {
  if (param.schedules.length >= MAX_SCHEDULES) {
    ElMessage.warning(t('building.schedule.maxGroupsHint', { max: MAX_SCHEDULES }))
    return
  }
  param.schedules.push(createRatiosSchedule(t('building.schedule.dayGroupName') + ' ' + (param.schedules.length + 1)))
  markDirty()
  queueConflictCheck()
}

function removeScheduleAt(param: ParamConfig, idx: number) {
  param.schedules.splice(idx, 1)
  if (param.schedules.length === 0) {
    // Always keep at least one — re-add a default
    param.schedules.push(createOfficeRatiosSchedule(t('building.schedule.presetWeekday')))
  }
  markDirty()
  queueConflictCheck()
}

function ensureScheduledParam(param: ParamConfig): ParamConfig {
  param.mode = 'scheduled'
  if (param.schedules.length === 0) param.schedules.push(createSchedule(param.fixed_value))
  return param
}

function getSetpointParam(zone: BuildingZone, key: string): ParamConfig {
  return ensureScheduledParam(getParam(zone, key))
}

function copyScheduleMeta(source: DaySchedule, target: DaySchedule) {
  target.name = source.name
  target.start_month = source.start_month
  target.start_day = source.start_day
  target.end_month = source.end_month
  target.end_day = source.end_day
  target.days = [...source.days]
  target.hours = [...source.hours]
}

function getCombinedSetpointParams(zone: BuildingZone) {
  const temperature = getSetpointParam(zone, 'temperature')
  const humidity = getSetpointParam(zone, 'relative_humidity')
  const count = Math.max(1, temperature.schedules.length, humidity.schedules.length)
  while (temperature.schedules.length < count) temperature.schedules.push(createSchedule(temperature.fixed_value))
  while (humidity.schedules.length < count) humidity.schedules.push(createSchedule(humidity.fixed_value))
  temperature.schedules.forEach((schedule, index) => copyScheduleMeta(schedule, humidity.schedules[index]))
  return { temperature, humidity, relative_humidity: humidity }
}

function addCombinedSetpointSchedule(zone: BuildingZone) {
  const { temperature, humidity } = getCombinedSetpointParams(zone)
  if (temperature.schedules.length >= MAX_SCHEDULES) return
  temperature.schedules.push(createSchedule(temperature.fixed_value))
  humidity.schedules.push(createSchedule(humidity.fixed_value))
  markDirty()
  queueConflictCheck()
}

function removeCombinedSetpointSchedule(zone: BuildingZone, index: number) {
  const { temperature, humidity } = getCombinedSetpointParams(zone)
  temperature.schedules.splice(index, 1)
  humidity.schedules.splice(index, 1)
  if (temperature.schedules.length === 0) {
    temperature.schedules.push(createSchedule(temperature.fixed_value))
    humidity.schedules.push(createSchedule(humidity.fixed_value))
  }
  markDirty()
  queueConflictCheck()
}

function normalizeScheduleHours(schedule: DaySchedule): DaySchedule {
  if (Array.isArray(schedule.hourly_ratios) && schedule.hourly_ratios.length === 24) {
    schedule.hours = schedule.hourly_ratios
      .map((value, hour) => value >= 50 ? hour : -1)
      .filter(hour => hour >= 0)
  }
  return schedule
}

function updateCombinedSetpointSchedule(zone: BuildingZone, index: number, value: DaySchedule) {
  const { temperature, humidity } = getCombinedSetpointParams(zone)
  const next = normalizeScheduleHours({ ...value, value: temperature.schedules[index].value })
  temperature.schedules[index] = next
  copyScheduleMeta(next, humidity.schedules[index])
  markDirty()
  queueConflictCheck()
}

function updateCombinedSetpointValue(zone: BuildingZone, index: number, key: 'temperature' | 'relative_humidity', value: number | undefined) {
  if (value === undefined) return
  const params = getCombinedSetpointParams(zone)
  params[key].schedules[index].value = value
  params[key].fixed_value = value
  markDirty()
  queueConflictCheck()
}

function updateScheduleAt(param: ParamConfig, index: number, value: DaySchedule) {
  param.schedules[index] = value
  markDirty()
  queueConflictCheck()
}

// ----- Conflict detection -----
function dateToNum(m: number, d: number): number {
  return m * 100 + d
}

function dateRangesOverlap(a: DaySchedule, b: DaySchedule): boolean {
  const aStart = dateToNum(a.start_month, a.start_day)
  const aEnd = dateToNum(a.end_month, a.end_day)
  const bStart = dateToNum(b.start_month, b.start_day)
  const bEnd = dateToNum(b.end_month, b.end_day)
  // Handle wrap-around (e.g., Nov 1 - Feb 28)
  if (aStart <= aEnd && bStart <= bEnd) {
    return aStart <= bEnd && bStart <= aEnd
  }
  // If either range wraps around the year, conservatively say they overlap
  return true
}

function schedulesConflict(a: DaySchedule, b: DaySchedule): boolean {
  if (!dateRangesOverlap(a, b)) return false
  const commonDays = a.days.filter(d => b.days.includes(d))
  if (commonDays.length === 0) return false
  const commonHours = a.hours.filter(h => b.hours.includes(h))
  return commonHours.length > 0
}

/** Conflict for internal-gain bar-chart schedules: date overlap + day-of-week overlap (no hour check). */
function schedulesConflictByDays(a: DaySchedule, b: DaySchedule): boolean {
  if (!dateRangesOverlap(a, b)) return false
  const commonDays = a.days.filter(d => b.days.includes(d))
  return commonDays.length > 0
}

const DOW_NAMES_ZH = ['', '一', '二', '三', '四', '五', '六', '日']

/** Get human-readable conflict description for schedule[idx], or '' if no conflict. */
function getInternalScheduleConflictMsg(schedules: DaySchedule[], idx: number): string {
  const cur = schedules[idx]
  if (!cur) return ''
  const conflicts: string[] = []
  for (let j = 0; j < schedules.length; j++) {
    if (j === idx) continue
    const other = schedules[j]
    if (!schedulesConflictByDays(cur, other)) continue
    // Compute intersection
    const aS = dateToNum(cur.start_month, cur.start_day)
    const aE = dateToNum(cur.end_month, cur.end_day)
    const bS = dateToNum(other.start_month, other.start_day)
    const bE = dateToNum(other.end_month, other.end_day)
    const lo = Math.max(aS, bS)
    const hi = Math.min(aE, bE)
    const loM = Math.floor(lo / 100), loD = lo % 100
    const hiM = Math.floor(hi / 100), hiD = hi % 100
    const days = cur.days.filter(d => other.days.includes(d))
    const daysStr = days.map(d => '周' + DOW_NAMES_ZH[d]).join('、')
    const otherName = other.name || `日程${j + 1}`
    conflicts.push(`与「${otherName}」在 ${loM}/${loD}~${hiM}/${hiD} ${daysStr} 重叠`)
  }
  return conflicts.join('；')
}

function getConflicts(schedules: DaySchedule[]): [number, number][] {
  const conflicts: [number, number][] = []
  for (let i = 0; i < schedules.length; i++) {
    for (let j = i + 1; j < schedules.length; j++) {
      if (schedulesConflict(schedules[i], schedules[j])) {
        conflicts.push([i, j])
      }
    }
  }
  return conflicts
}

// ----- Check if a specific schedule index is in conflict -----
function isScheduleInConflict(schedules: DaySchedule[], idx: number): boolean {
  for (let j = 0; j < schedules.length; j++) {
    if (j === idx) continue
    if (schedulesConflict(schedules[idx], schedules[j])) return true
  }
  return false
}

const ALL_PARAM_METAS = [...PARAM_METAS, ...SETPOINT_METAS]
void ALL_PARAM_METAS

// ----- Global conflict check (debounced for performance) -----
const hasAnyConflict = ref(false)
let _conflictTimer: ReturnType<typeof setTimeout> | null = null

function _checkConflicts() {
  for (const zone of editZones.value) {
    // Internal gains: use day-based conflict (no hour check)
    for (const pm of PARAM_METAS) {
      const param = getParam(zone, pm.key)
      if (param.mode === 'scheduled') {
        for (let i = 0; i < param.schedules.length; i++) {
          if (getInternalScheduleConflictMsg(param.schedules, i)) {
            hasAnyConflict.value = true
            return
          }
        }
      }
    }
    // Setpoints: legacy hour-based conflict
    for (const pm of SETPOINT_METAS) {
      const param = getParam(zone, pm.key)
      if (param.mode === 'scheduled' && getConflicts(param.schedules).length > 0) {
        hasAnyConflict.value = true
        return
      }
    }
  }
  hasAnyConflict.value = false
}

function queueConflictCheck() {
  if (_conflictTimer) clearTimeout(_conflictTimer)
  _conflictTimer = setTimeout(_checkConflicts, 500)
}

// ----- Unsaved changes detection (version-based) -----
const editVersion = ref(0)
const savedVersion = ref(0)
const _initializing = ref(true)
const isDirty = computed(() => editVersion.value !== savedVersion.value)

function markDirty() {
  if (_initializing.value) return
  editVersion.value++
  scheduleSyncToSelected()
}

function handleZoneFormInput() {
  markDirty()
}

function handleZoneFormChange() {
  markDirty()
  queueConflictCheck()
}

// markDirty 会被各种表单/调度修改调用；这里用一帧合并同步到已选分区。
let syncFrameId: number | null = null
function scheduleSyncToSelected() {
  if (syncFrameId !== null) return
  const source = activeZone.value
  const set = selectedSet.value
  if (!source || !zoneSelectMode.value || set.size <= 1 || !set.has(source)) return
  syncFrameId = requestAnimationFrame(() => {
    syncFrameId = null
    syncActiveZoneToSelected()
  })
}
function syncActiveZoneToSelected() {
  const source = activeZone.value
  if (!source) return
  const set = selectedSet.value
  if (!zoneSelectMode.value || set.size <= 1 || !set.has(source)) return
  set.forEach(target => {
    if (target !== source) syncZoneDetailSettings(source, target)
  })
}

const zoneItems = computed(() => editZones.value.map((zone, index) => ({ zone, index })))
const zoneListRef = ref<HTMLElement | null>(null)
const zoneListScrollTop = ref(0)
const zoneListHeight = ref(0)
const zoneListWidth = ref(0)
let zoneListResizeObserver: ResizeObserver | null = null
const ZONE_GRID_OVERSCAN_ROWS = 4

const zoneGridGap = computed(() => isMobile.value ? 8 : 12)
const zoneCardOuterHeight = computed(() => (isMobile.value ? 44 : 54) + zoneGridGap.value)
const zoneGridColumns = computed(() => {
  if (isMobile.value) return 2
  const minCardWidth = 260
  return Math.max(1, Math.floor((zoneListWidth.value + zoneGridGap.value) / (minCardWidth + zoneGridGap.value)))
})
const totalZoneRows = computed(() => Math.ceil(zoneItems.value.length / zoneGridColumns.value))
const firstVisibleZoneRow = computed(() => Math.max(0, Math.floor(zoneListScrollTop.value / zoneCardOuterHeight.value) - ZONE_GRID_OVERSCAN_ROWS))
const visibleZoneRowCount = computed(() => Math.ceil(zoneListHeight.value / zoneCardOuterHeight.value) + ZONE_GRID_OVERSCAN_ROWS * 2)
const lastVisibleZoneRow = computed(() => Math.min(totalZoneRows.value, firstVisibleZoneRow.value + visibleZoneRowCount.value))
const visibleZoneItems = computed(() => {
  const start = firstVisibleZoneRow.value * zoneGridColumns.value
  const end = lastVisibleZoneRow.value * zoneGridColumns.value
  return zoneItems.value.slice(start, end)
})
const zoneTopSpacerHeight = computed(() => firstVisibleZoneRow.value * zoneCardOuterHeight.value)
const zoneBottomSpacerHeight = computed(() => Math.max(0, (totalZoneRows.value - lastVisibleZoneRow.value) * zoneCardOuterHeight.value))

watch([isMobile, () => editZones.value.length], () => nextTick(updateZoneListMetrics))

function updateZoneListMetrics() {
  const el = zoneListRef.value
  if (!el) return
  zoneListHeight.value = el.clientHeight
  zoneListWidth.value = el.clientWidth
  zoneListScrollTop.value = el.scrollTop
}

function handleZoneListScroll() {
  zoneListScrollTop.value = zoneListRef.value?.scrollTop || 0
}

function scrollZoneListToBottom() {
  nextTick(() => {
    const el = zoneListRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
    updateZoneListMetrics()
  })
}

// ----- Zone management -----
const MAX_ZONES = 999 // 最大分区数
const activeZone = computed(() => editZones.value[selectedZoneIdx.value] ?? null)

// ----- Table selection for batch operations -----
// 使用 Set 直接存储被选中的 zone 引用，避免数组 ↔ Set 反复转换带来的 O(n) 开销。
// 配合 shallowRef + triggerRef，在 add/delete/clear 后手动通知 Vue 更新依赖。
const selectedSet = shallowRef<Set<BuildingZone>>(new Set())
const selectedCount = computed(() => selectedSet.value.size)
const zoneSelectMode = ref(false)
const batchAddVisible = ref(false)
const batchAddCount = ref(3)
const batchAddName = ref('')

function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

function isZoneSelected(zone: BuildingZone): boolean {
  return selectedSet.value.has(zone)
}

function toggleZoneSelect(zone: BuildingZone, checked: any, _index?: number) {
  // 勾选仅更新选中集，不切换 activeZone，以避免详情面板重渲染。
  if (checked) {
    if (!selectedSet.value.has(zone)) {
      selectedSet.value.add(zone)
      triggerRef(selectedSet)
    }
  } else {
    if (selectedSet.value.delete(zone)) triggerRef(selectedSet)
  }
}

function setZoneSelectMode(enabled: any) {
  zoneSelectMode.value = Boolean(enabled)
  if (!zoneSelectMode.value && selectedSet.value.size > 0) {
    selectedSet.value.clear()
    triggerRef(selectedSet)
  }
}

function handleZoneCardClick(zone: BuildingZone, index?: number) {
  if (zoneSelectMode.value) {
    // 选择模式下，点击卡片主体也只切换勾选状态，不进入详情。
    toggleZoneSelect(zone, !selectedSet.value.has(zone), index)
    return
  }
  if (typeof index === 'number' && index >= 0) {
    selectedZoneIdx.value = index
    activePresetKey.value = ''
  } else {
    handleRowClick(zone)
  }
}

// 详情面板始终只绑定当前 activeZone；多选时通过 markDirty 自动同步到其他已选分区。
const isBatchDetailEditing = computed(() => false)

function syncZoneDetailSettings(source: BuildingZone, target: BuildingZone) {
  target.name = source.name
  target.area = source.area
  target.floor_height = source.floor_height
  target.zone_position = source.zone_position
  target.wall_config = cloneValue(source.wall_config)
  target.wall_u_value = source.wall_u_value
  target.window_u_value = source.window_u_value
  target.window_wall_ratio = source.window_wall_ratio
  target.roof_u_value = source.roof_u_value
  target.people_density = cloneValue(source.people_density)
  target.people_heat_gain = source.people_heat_gain
  target.lighting_density = cloneValue(source.lighting_density)
  target.equipment_density = cloneValue(source.equipment_density)
  target.fresh_air_volume = cloneValue(source.fresh_air_volume)
  target.temperature = cloneValue(source.temperature)
  target.relative_humidity = cloneValue(source.relative_humidity)
}

function detailEditTargets(): BuildingZone[] {
  const zone = activeZone.value
  return zone ? [zone] : []
}

function getSharedValue<T>(getter: (zone: BuildingZone) => T): T | undefined {
  const targets = detailEditTargets()
  if (targets.length === 0) return undefined
  const firstValue = getter(targets[0])
  return targets.every(zone => getter(zone) === firstValue) ? firstValue : undefined
}

type EditableZoneField = 'name' | 'area' | 'floor_height' | 'zone_position'

function getZoneFieldValue(field: EditableZoneField): string | number | ZonePosition | undefined {
  return getSharedValue(zone => zone[field])
}

function setZoneFieldValue(field: EditableZoneField, value: string | number | ZonePosition | undefined) {
  if (value === undefined) return
  detailEditTargets().forEach(zone => {
    ;(zone as any)[field] = value
  })
  markDirty()
}

function getDetailParamFixedValue(key: string): number | undefined {
  return getSharedValue(zone => getParam(zone, key).fixed_value)
}

function setDetailParamFixedValue(key: string, value: number | undefined) {
  if (value === undefined) return
  detailEditTargets().forEach(zone => {
    getParam(zone, key).fixed_value = value
  })
  markDirty()
}

function getPeopleHeatGainValue(): number | undefined {
  return getSharedValue(zone => zone.people_heat_gain)
}

function setPeopleHeatGainValue(value: number | undefined) {
  if (value === undefined) return
  detailEditTargets().forEach(zone => {
    zone.people_heat_gain = value
  })
  markDirty()
}

watch(activeZone, () => {
  // 不再使用 deep watch 自动同步多个 zone；改为表单事件触发（见 scheduleSyncToSelected）。
})

const allPagedSelected = computed(() => {
  const set = selectedSet.value
  return editZones.value.length > 0 && editZones.value.every(zone => set.has(zone))
})

const someSelected = computed(() =>
  selectedSet.value.size > 0 && !allPagedSelected.value
)

function toggleAllPaged(checked: any) {
  if (checked) {
    const set = selectedSet.value
    editZones.value.forEach(zone => set.add(zone))
  } else {
    selectedSet.value.clear()
  }
  triggerRef(selectedSet)
}

function handleRowClick(row: BuildingZone) {
  const idx = editZones.value.indexOf(row)
  if (idx >= 0) {
    selectedZoneIdx.value = idx
    activePresetKey.value = ''
  }
}

function addZone() {
  if (editZones.value.length >= MAX_ZONES) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  editZones.value.push(createDefaultZone())
  markDirty()
  scrollZoneListToBottom()
  nextTick(() => {
    selectedZoneIdx.value = editZones.value.length - 1
    activePresetKey.value = ''
  })
}

function copyZone(zone: BuildingZone) {
  if (editZones.value.length >= MAX_ZONES) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  const copy: BuildingZone = JSON.parse(JSON.stringify(zone))
  editZones.value.push(copy)
  markDirty()
  scrollZoneListToBottom()
  nextTick(() => {
    selectedZoneIdx.value = editZones.value.length - 1
  })
  ElMessage.success(t('building.zone.copySuccess'))
}

function removeZone(zone: BuildingZone) {
  if (editZones.value.length <= 1) {
    ElMessage.warning(t('building.zone.lastZoneHint'))
    return
  }
  const idx = editZones.value.indexOf(zone)
  if (idx < 0) return
  editZones.value.splice(idx, 1)
  markDirty()
  if (selectedZoneIdx.value >= editZones.value.length) {
    selectedZoneIdx.value = editZones.value.length - 1
  }
}

async function batchDelete() {
  const size = selectedSet.value.size
  if (size === 0) return
  if (size >= editZones.value.length) {
    ElMessage.warning(t('building.zone.lastZoneHint'))
    return
  }
  await ElMessageBox.confirm(
    t('building.zone.batchDeleteConfirm', { count: size }),
    t('common.warning'), { type: 'warning' }
  )
  const toRemove = selectedSet.value
  editZones.value = editZones.value.filter(z => !toRemove.has(z))
  selectedZoneIdx.value = Math.min(selectedZoneIdx.value, editZones.value.length - 1)
  selectedSet.value = new Set()
  triggerRef(selectedSet)
  markDirty()
}

function batchCopy() {
  if (selectedSet.value.size === 0) return
  const remaining = MAX_ZONES - editZones.value.length
  if (remaining <= 0) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  const toCopy = Array.from(selectedSet.value).slice(0, remaining)
  const copies = toCopy.map(z => {
    const copy: BuildingZone = JSON.parse(JSON.stringify(z))
    return copy
  })
  editZones.value.push(...copies)
  markDirty()
  scrollZoneListToBottom()
  ElMessage.success(t('building.zone.batchCopySuccess', { count: copies.length }))
}

function confirmBatchAdd() {
  const remaining = MAX_ZONES - editZones.value.length
  if (remaining <= 0) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  const count = Math.max(1, Math.min(batchAddCount.value, 200, remaining))
  const nicknamePrefix = batchAddName.value.trim()
  for (let i = 0; i < count; i++) {
    const name = nicknamePrefix ? `${nicknamePrefix} ${editZones.value.length + 1}` : ''
    editZones.value.push(createDefaultZone(name))
  }
  markDirty()
  scrollZoneListToBottom()
  batchAddVisible.value = false
  ElMessage.success(t('building.zone.batchAddSuccess', { count }))
}

// ----- Computed total area -----
const totalArea = computed(() => editZones.value.reduce((sum, z) => sum + (z.area || 0), 0))

// ----- Normalize zone from stored data (backward compat) -----
function normalizeSchedule(raw: any): DaySchedule {
  // Handle old format with slots: TimeSlot[] or new format
  if (raw.hours !== undefined) {
    return raw as DaySchedule
  }
  // Convert old slot-based format
  if (raw.slots && raw.slots.length > 0) {
    const slot = raw.slots[0]
    const hours: number[] = []
    for (let h = (slot.start_hour || 0); h < (slot.end_hour || 24); h++) hours.push(h)
    return {
      name: raw.name || '',
      start_month: 1, start_day: 1, end_month: 12, end_day: 31,
      days: raw.days || [1, 2, 3, 4, 5, 6, 7],
      hours,
      value: slot.value || 0,
    }
  }
  return createSchedule(0, raw.name || '')
}


function normalizeZoneNickname(rawName: any): string {
  const name = String(rawName || '').trim()
  return /^(分区|Zone)\s*\d+$/i.test(name) ? '' : name
}
function normalizeZone(raw: any): BuildingZone {
  const toParam = (val: any, fallback: number): ParamConfig => {
    if (val && typeof val === 'object' && 'mode' in val) {
      const pc = val as ParamConfig
      return {
        ...pc,
        schedules: (pc.schedules || []).map(normalizeSchedule),
      }
    }
    return createParamConfig(typeof val === 'number' ? val : fallback)
  }
  const defaultWallCfg: WallConfig = { south_exterior: true, north_exterior: true, east_exterior: true, west_exterior: true }
  return {
    name: normalizeZoneNickname(raw.name),
    area: raw.area || 0,
    floor_height: raw.floor_height ?? 3.5,
    zone_position: raw.zone_position ?? 'single',
    wall_config: raw.wall_config ? { ...defaultWallCfg, ...raw.wall_config } : defaultWallCfg,
    wall_u_value: raw.wall_u_value ?? 1.0,
    window_u_value: raw.window_u_value ?? 3.0,
    window_wall_ratio: raw.window_wall_ratio ?? 0.4,
    roof_u_value: raw.roof_u_value ?? 0.8,
    people_density: toParam(raw.people_density, 0.1),
    people_heat_gain: typeof raw.people_heat_gain === 'number' ? raw.people_heat_gain : 134,
    lighting_density: toParam(raw.lighting_density, 10),
    equipment_density: toParam(raw.equipment_density, 15),
    fresh_air_volume: toParam(raw.fresh_air_volume, 30),
    temperature: toParam(raw.temperature, 26),
    relative_humidity: toParam(raw.relative_humidity, 50),
  }
}

// ----- Init -----
onMounted(async () => {
  const { data } = await getBuilding(projectId, buildingId)
  building.value = data
  editType.value = data.building_type
  editClimateZone.value = data.climate_zone || ''
  if (data.zones && data.zones.length > 0) {
    editZones.value = data.zones.map(normalizeZone)
  } else {
    const ep = data.envelope_params || {}
    editZones.value = [{
      name: '',
      area: data.total_area || 0,
      floor_height: 3.5,
      zone_position: 'single' as ZonePosition,
      wall_config: { south_exterior: true, north_exterior: true, east_exterior: true, west_exterior: true },
      wall_u_value: ep.wall_u_value ?? 1.0,
      window_u_value: ep.window_u_value ?? 3.0,
      window_wall_ratio: ep.window_wall_ratio ?? 0.4,
      roof_u_value: ep.roof_u_value ?? 0.8,
      people_density: createParamConfig(ep.people_density ?? 0.1),
      lighting_density: createParamConfig(ep.lighting_density ?? 10),
      equipment_density: createParamConfig(ep.equipment_density ?? 15),
      fresh_air_volume: createParamConfig(ep.fresh_air_volume ?? 30),
      temperature: createParamConfig(26),
      relative_humidity: createParamConfig(50),
    }]
  }
  // Migrate internal-gain params to scheduled mode (with default schedule if empty)
  for (const z of editZones.value) {
    for (const k of INTERNAL_GAIN_KEYS) {
      normalizeInternalGainParam((z as any)[k])
    }
  }
  _checkConflicts()
  nextTick(() => {
    updateZoneListMetrics()
    if (zoneListRef.value) {
      zoneListResizeObserver = new ResizeObserver(updateZoneListMetrics)
      zoneListResizeObserver.observe(zoneListRef.value)
    }
    savedVersion.value = editVersion.value
    // Allow dirty detection after initial load settles (debounce is 500ms)
    setTimeout(() => { _initializing.value = false }, 600)
  })
  window.addEventListener('beforeunload', handleBeforeUnload)
})

// ----- Validation -----
function validateZones(): string | null {
  for (let i = 0; i < editZones.value.length; i++) {
    const z = editZones.value[i]
    const label = z.name || `${t('building.zone.title')} ${i + 1}`
    if (!z.area || z.area < 0.1 || z.area > 9999.9) return `${label}: ${t('building.zone.area')} ${t('building.validation.rangeValue', { min: 0.1, max: 9999.9 })}`
    if (!z.floor_height || z.floor_height < 1 || z.floor_height > 100) return `${label}: ${t('building.zone.floorHeight')} ${t('building.validation.rangeValue', { min: 1, max: 100 })}`
    if (z.wall_u_value < 0.01) return `${label}: ${t('building.envelope.wallU')} ${t('building.validation.minValue', { min: 0.01 })}`
    if (z.window_u_value < 0.1) return `${label}: ${t('building.envelope.windowU')} ${t('building.validation.minValue', { min: 0.1 })}`
    if (z.roof_u_value < 0.01) return `${label}: ${t('building.envelope.roofU')} ${t('building.validation.minValue', { min: 0.01 })}`
  }
  return null
}

// ----- Save -----
async function handleSave() {
  if (hasAnyConflict.value) {
    ElMessage.error(t('building.schedule.cannotSaveConflict'))
    return
  }
  const validationError = validateZones()
  if (validationError) {
    ElMessage.error(validationError)
    return
  }

  // Check if zones changed — if so, simulation results will be cleared
  const zonesChanged = JSON.stringify(editZones.value) !== JSON.stringify(building.value?.zones)
  if (zonesChanged) {
    try {
      const { data: sims } = await getSimulations(buildingId)
      if (sims.length > 0) {
        await ElMessageBox.confirm(
          t('building.simClearWarning'),
          t('common.warning'),
          { type: 'warning', confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel') }
        )
      }
    } catch (e: any) {
      if (e === 'cancel' || e?.message === 'cancel') return
      // If getSimulations fails, proceed without warning
    }
  }

  saving.value = true
  try {
    const update: BuildingUpdate = {
      building_type: editType.value,
      climate_zone: editClimateZone.value || undefined,
      total_area: totalArea.value,
      zones: editZones.value,
    }
    const { data } = await updateBuilding(projectId, buildingId, update)
    building.value = data
    ElMessage.success(t('building.updateSuccess'))
    savedVersion.value = editVersion.value
  } finally {
    saving.value = false
  }
}

function goBackToList() {
  router.push(`/projects/${projectId}/building`)
}

// ----- Unsaved changes guards -----
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (isDirty.value) {
    e.preventDefault()
  }
}

onBeforeRouteLeave(async () => {
  if (isDirty.value) {
    try {
      await ElMessageBox.confirm(t('building.unsavedWarning'), t('common.warning'), { type: 'warning' })
    } catch {
      return false
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  zoneListResizeObserver?.disconnect()
  zoneListResizeObserver = null
})

</script>

<template>
  <div class="building-view" v-if="building">
    <Teleport v-if="isMobile" to="#ws-mobile-topbar-slot" defer>
      <div class="building-mobile-topbar">
        <div class="building-mb-left">
          <button class="building-mb-back" :aria-label="t('workspace.backToProjects') || '返回'" @click="goBackToList">
            <el-icon :size="20">
              <ArrowLeft />
            </el-icon>
          </button>
          <span class="building-mb-area">{{ totalArea.toFixed(1) }} m²</span>
        </div>
        <div class="building-mb-title">{{ t('building.zone.title') }} ({{ editZones.length }})</div>
        <div class="building-mb-actions">
          <button class="building-mb-icon-btn" :aria-label="t('building.zone.add')" @click="addZone">
            <el-icon :size="16"><Plus /></el-icon>
          </button>
          <button v-if="zoneSelectMode" class="building-mb-icon-btn building-mb-icon-btn--danger" :disabled="selectedCount === 0"
            :aria-label="t('building.zone.batchDelete')" @click="batchDelete">
            <el-icon :size="16"><Delete /></el-icon>
          </button>
          <el-badge is-dot :hidden="!isDirty" type="danger" class="building-mb-save-badge">
            <button class="building-mb-save" :disabled="saving || hasAnyConflict" :aria-label="t('common.save')"
              @click="handleSave">
              <el-icon v-if="!saving" :size="16">
                <FolderChecked />
              </el-icon>
              <el-icon v-else :size="16" class="is-loading">
                <Setting />
              </el-icon>
            </button>
          </el-badge>
        </div>
      </div>
    </Teleport>

    <!-- Compact header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-name-row">
          <h1>{{ building.name }}</h1>
          <el-tag type="success" effect="plain" size="large" class="area-tag">{{ totalArea.toFixed(1) }} m²</el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="saving" :disabled="hasAnyConflict" @click="handleSave">{{ t('common.save')
          }}</el-button>
      </div>
    </div>

    <!-- Zone table + batch toolbar -->
    <el-card class="zone-table-card" shadow="never">
      <template v-if="!isMobile" #header>
        <div class="zone-table-header">
          <span class="zone-table-title">{{ t('building.zone.title') }} ({{ editZones.length }})</span>
          <div class="zone-table-actions">
            <el-button type="primary" :icon="Plus" size="small" @click="addZone">
              <span v-if="!isMobile">{{ t('building.zone.add') }}</span>
            </el-button>
            <el-button :icon="FolderAdd" size="small" @click="batchAddVisible = true">
              <span v-if="!isMobile">{{ t('building.zone.batchAdd') }}</span>
            </el-button>
            <el-button v-if="zoneSelectMode" :icon="CopyDocument" size="small" :disabled="selectedCount === 0" @click="batchCopy">
              <span v-if="!isMobile">{{ t('building.zone.batchCopy') }}</span>
            </el-button>
            <el-button v-if="zoneSelectMode" type="danger" :icon="Delete" size="small" plain :disabled="selectedCount === 0"
              @click="batchDelete">
              <span v-if="!isMobile">{{ t('building.zone.batchDelete') }}</span>
            </el-button>
          </div>
        </div>
      </template>

      <div class="zone-grid" :class="{ 'is-zone-select-mode': zoneSelectMode }">
        <div class="zone-grid-toolbar">
          <el-switch :model-value="zoneSelectMode" :active-text="t('building.zone.selectMode')"
            @change="setZoneSelectMode" />
          <el-checkbox v-if="zoneSelectMode" :model-value="allPagedSelected" :indeterminate="someSelected"
            @change="(v: any) => toggleAllPaged(v)">
            {{ t('common.selectAll') }}
          </el-checkbox>
          <span v-if="zoneSelectMode && selectedCount > 0" class="zg-sel-count">
            {{ t('building.zone.selectedCount', { count: selectedCount }) }}
          </span>
        </div>
        <div ref="zoneListRef" class="zone-grid-scroll" @scroll="handleZoneListScroll">
          <div :style="{ height: `${zoneTopSpacerHeight}px` }" />
          <div class="zone-grid-list">
            <div v-for="item in visibleZoneItems" :key="item.index" class="zone-mini-card"
              :class="{ active: item.index === selectedZoneIdx, selected: zoneSelectMode && isZoneSelected(item.zone) }"
              @click="handleZoneCardClick(item.zone, item.index)">
              <div class="zmc-header">
                <el-checkbox v-if="zoneSelectMode" :model-value="isZoneSelected(item.zone)" @click.stop
                  @change="(v: any) => toggleZoneSelect(item.zone, v, item.index)" />
                <span class="zmc-num">#{{ item.index + 1 }}</span>
                <span class="zmc-area">{{ (item.zone.area || 0).toFixed(1) }} m²</span>
                <span v-if="item.zone.name && (!isMobile || zoneSelectMode)" class="zmc-nickname" :title="item.zone.name">{{ item.zone.name }}</span>
                <div v-if="!zoneSelectMode" class="zmc-actions" @click.stop>
                  <el-button class="bv-action-btn zmc-action-btn" text circle type="primary" size="small" :icon="CopyDocument" :title="t('building.zone.copy')"
                    @click="copyZone(item.zone)" />
                  <el-button class="bv-action-btn zmc-action-btn" text circle type="danger" size="small" :icon="Delete" :disabled="editZones.length <= 1"
                    :title="t('building.zone.delete')" @click="removeZone(item.zone)" />
                </div>
              </div>
            </div>
          </div>
          <div :style="{ height: `${zoneBottomSpacerHeight}px` }" />
        </div>
      </div>
    </el-card>

    <!-- Batch add dialog -->
    <el-dialog v-model="batchAddVisible" :title="t('building.zone.batchAdd')" width="400px">
      <el-form label-width="100px">
        <el-form-item :label="t('building.zone.batchAddCount')">
          <el-input-number v-model="batchAddCount" :min="1" :max="200" />
        </el-form-item>
        <el-form-item :label="t('building.zone.batchAddPrefix')">
          <el-input v-model="batchAddName" :maxlength="20" :placeholder="t('building.zone.batchAddPrefixHint')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchAddVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmBatchAdd">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- Active zone detail -->
    <el-card v-if="activeZone" class="zone-card" shadow="never">
      <template #header>
        <div class="zone-detail-header">
          <div class="zone-detail-title">
            <span>#{{ selectedZoneIdx + 1 }}<template v-if="activeZone.name"> · {{ activeZone.name }}</template> — {{
              t('building.zone.detailEdit') }}</span>
          </div>
          <div class="zone-detail-actions">
            <el-dropdown trigger="click" @command="applyPreset">
              <el-button size="small">
                {{ activePresetKey ? t(`building.zone.presets.${activePresetKey}`) : t('building.applyTemplate') }}
                <el-icon class="el-icon--right">
                  <ArrowDown />
                </el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="pk in PRESET_KEYS" :key="pk" :command="pk">
                    {{ t(`building.zone.presets.${pk}`) }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>
      <el-form label-position="top" class="zone-form" @input.capture="handleZoneFormInput" @change.capture="handleZoneFormChange">
        <div class="zone-basic-row">
          <div class="zone-basic-field">
            <el-form-item :label="t('building.zone.nickname')" class="zone-nickname-item zone-inline-item">
              <el-input :model-value="getZoneFieldValue('name') as string | undefined" clearable :maxlength="32"
                :placeholder="isBatchDetailEditing ? t('building.zone.mixedValue') : t('building.zone.nicknamePlaceholder')"
                @update:model-value="(value: string) => setZoneFieldValue('name', value)" />
            </el-form-item>
          </div>
          <div class="zone-basic-field">
            <el-form-item :label="t('building.zone.area')" class="zone-inline-item">
              <el-input-number :model-value="getZoneFieldValue('area') as number | undefined" :min="0.1" :max="9999.9" :precision="1" :controls="false"
                :placeholder="isBatchDetailEditing ? t('building.zone.mixedValue') : ''" class="zone-basic-number"
                @update:model-value="(value: number | undefined) => setZoneFieldValue('area', value)" />
            </el-form-item>
          </div>
          <div class="zone-basic-field">
            <el-form-item :label="t('building.zone.floorHeight')" class="zone-inline-item">
              <el-input-number :model-value="getZoneFieldValue('floor_height') as number | undefined" :min="1" :max="100" :precision="1" :controls="false"
                :placeholder="isBatchDetailEditing ? t('building.zone.mixedValue') : ''" class="zone-basic-number"
                @update:model-value="(value: number | undefined) => setZoneFieldValue('floor_height', value)" />
            </el-form-item>
          </div>
          <div class="zone-basic-field">
            <el-form-item :label="t('building.envelope.zonePosition')" class="zone-inline-item">
              <el-select :model-value="getZoneFieldValue('zone_position') as ZonePosition | undefined" class="zone-basic-select"
                :placeholder="isBatchDetailEditing ? t('building.zone.mixedValue') : ''"
                @update:model-value="(value: ZonePosition) => setZoneFieldValue('zone_position', value)">
                <el-option value="single" :label="t('building.envelope.position.single')" />
                <el-option value="top" :label="t('building.envelope.position.top')" />
                <el-option value="middle" :label="t('building.envelope.position.middle')" />
                <el-option value="bottom" :label="t('building.envelope.position.bottom')" />
              </el-select>
            </el-form-item>
          </div>
        </div>

        <!-- Wall exterior config -->
        <el-row :gutter="16">
          <el-col :xs="24" :sm="24">
            <el-form-item :label="t('building.envelope.wallType')" class="wall-config-item">
              <div class="wall-config-group">
                <el-checkbox v-model="activeZone.wall_config.south_exterior">{{ t('building.envelope.wallDir.south')
                  }}</el-checkbox>
                <el-checkbox v-model="activeZone.wall_config.north_exterior">{{ t('building.envelope.wallDir.north')
                  }}</el-checkbox>
                <el-checkbox v-model="activeZone.wall_config.east_exterior">{{ t('building.envelope.wallDir.east')
                  }}</el-checkbox>
                <el-checkbox v-model="activeZone.wall_config.west_exterior">{{ t('building.envelope.wallDir.west')
                  }}</el-checkbox>
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <div v-for="pm in PARAM_METAS" :key="pm.key" class="ig-param">
          <div class="ig-param-header">
            <span class="ig-param-label">{{ pm.key === 'people_density' ? t('building.internalGains.peopleShort') :
              t(pm.label) }}</span>
            <div class="ig-inline-controls">
              <div class="ig-unit-input">
              <el-input-number :model-value="getDetailParamFixedValue(pm.key)" :min="pm.min" :max="pm.max"
                :precision="pm.precision" :step="pm.step" :controls="false" size="small" class="ig-number"
                :placeholder="isBatchDetailEditing ? t('building.zone.mixedValue') : ''"
                @update:model-value="(value: number | undefined) => setDetailParamFixedValue(pm.key, value)" />
                <span class="ig-unit-text">{{ pm.key === 'people_density' ? '人/㎡' : paramUnit(pm.key) }}</span>
              </div>
              <template v-if="pm.key === 'people_density'">
                <span class="ig-multiply">×</span>
                <div class="ig-unit-input">
                  <el-input-number :model-value="getPeopleHeatGainValue()" :min="0" :max="500" :precision="0" :step="1"
                    :controls="false" size="small" class="ig-number ig-number--heat"
                    :placeholder="isBatchDetailEditing ? t('building.zone.mixedValue') : ''"
                    @update:model-value="(value: number | undefined) => setPeopleHeatGainValue(value)" />
                  <span class="ig-unit-text">W/人</span>
                </div>
              </template>
            </div>
            <el-button type="primary" plain size="small" :icon="Plus" class="ig-schedule-button"
              :disabled="getParam(activeZone, pm.key).schedules.length >= MAX_SCHEDULES"
              @click="addScheduleForParam(getParam(activeZone, pm.key))">
              {{ t('building.schedule.editor.schedule') }}
            </el-button>
          </div>
          <div class="ig-schedules">
            <ScheduleEditor v-for="(sch, sIdx) in getParam(activeZone, pm.key).schedules" :key="sIdx" :model-value="sch"
              :peak-value="getParam(activeZone, pm.key).fixed_value" :unit="paramUnit(pm.key)" :type="paramType(pm.key)"
              :param-label="t(pm.label)" :removable="getParam(activeZone, pm.key).schedules.length > 1"
              :conflict-message="getInternalScheduleConflictMsg(getParam(activeZone, pm.key).schedules, sIdx)"
              @update:model-value="(v: DaySchedule) => updateScheduleAt(getParam(activeZone, pm.key), sIdx, v)"
              @remove="removeScheduleAt(getParam(activeZone, pm.key), sIdx)" />
          </div>
        </div>

        <div class="param-row setpoint-param-row">
          <div class="param-header setpoint-param-header">
            <span class="param-label">{{ t('building.setpoint.combined') }}</span>
            <el-button type="primary" plain size="small" @click="addCombinedSetpointSchedule(activeZone)"
              :disabled="getCombinedSetpointParams(activeZone).temperature.schedules.length >= MAX_SCHEDULES">
              + {{ t('building.schedule.addDayGroup') }}
              ({{ getCombinedSetpointParams(activeZone).temperature.schedules.length }}/{{ MAX_SCHEDULES }})
            </el-button>
          </div>

          <div class="param-schedules setpoint-schedules">
            <ScheduleEditor v-for="(sch, sIdx) in getCombinedSetpointParams(activeZone).temperature.schedules" :key="sIdx"
              :model-value="sch" :index="sIdx" mode="binary" type="setpoint" :param-label="t('building.setpoint.combined')"
              :conflict-message="isScheduleInConflict(getCombinedSetpointParams(activeZone).temperature.schedules, sIdx) ? t('building.schedule.conflictWarning') : ''"
              :removable="getCombinedSetpointParams(activeZone).temperature.schedules.length > 1"
              @update:model-value="(value: DaySchedule) => updateCombinedSetpointSchedule(activeZone, sIdx, value)"
              @remove="removeCombinedSetpointSchedule(activeZone, sIdx)">
              <template #before-meta>
                <div class="setpoint-value-settings">
                  <div class="setpoint-value-row">
                    <span class="schedule-sub-label">{{ t('building.setpoint.temperature') }} ({{ paramUnit('temperature') }})</span>
                    <el-input-number :model-value="sch.value" :min="10" :max="35" :precision="1"
                      :step="0.5" :controls="false" size="small" class="setpoint-value-input"
                      @update:model-value="(value: number | undefined) => updateCombinedSetpointValue(activeZone, sIdx, 'temperature', value)" />
                  </div>
                  <div class="setpoint-value-row">
                    <span class="schedule-sub-label">{{ t('building.setpoint.humidity') }} ({{ paramUnit('relative_humidity') }})</span>
                    <el-input-number :model-value="getCombinedSetpointParams(activeZone).relative_humidity.schedules[sIdx].value" :min="20" :max="90" :precision="0"
                      :step="5" :controls="false" size="small" class="setpoint-value-input"
                      @update:model-value="(value: number | undefined) => updateCombinedSetpointValue(activeZone, sIdx, 'relative_humidity', value)" />
                  </div>
                </div>
              </template>
            </ScheduleEditor>
            <div class="schedule-note">{{ t('building.schedule.unspecifiedNote') }}</div>
          </div>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.building-view {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  --bv-button-press-scale: 0.96;
  --bv-icon-button-press-scale: 0.9;
  --bv-button-shadow: none;
  --bv-tap-highlight: transparent;
}

/* ---- Header ---- */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  flex-wrap: wrap;
  gap: 12px;
  padding: 18px 22px;
  border-radius: 14px;
  background: linear-gradient(135deg, #ecfeff 0%, #f0f9ff 60%, #faf5ff 100%);
  border: 1px solid rgba(8, 145, 178, 0.12);
}

.header-left {
  flex: 1;
  min-width: 0;
}

.header-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.header-name-row h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.area-tag {
  font-size: 14px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* ---- Zone table ---- */
.zone-table-card {
  margin-bottom: 16px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.zone-table-card :deep(.el-card__header) {
  padding: 14px 18px;
  background: #f8fafc;
}

.zone-table-card :deep(.el-card__body) {
  padding: 12px;
}

.zone-table-card :deep(.el-table) {
  width: 100%;
}

.zone-table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.zone-table-title {
  font-weight: 600;
  font-size: 15px;
}

.zone-table-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

:deep(.current-zone-row) {
  background-color: var(--el-color-primary-light-9) !important;
}

/* ---- Zone mini-card grid (replaces el-table) ---- */
.zone-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.zone-grid-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 2px;
  border-bottom: 1px dashed #e2e8f0;
  margin-bottom: 4px;
}

.zone-grid-toolbar :deep(.el-switch__label),
.zone-grid-toolbar :deep(.el-checkbox__label),
.zg-sel-count {
  font-size: 13px;
  font-weight: 500;
}

.zone-grid-toolbar :deep(.el-switch__label) {
  color: #475569;
}

.zone-grid-toolbar :deep(.el-switch__label.is-active) {
  color: #0891b2;
}

.zone-grid-toolbar :deep(.el-checkbox) {
  margin-left: auto;
}

.zg-sel-count {
  color: #0891b2;
}

.zone-grid-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr));
  gap: 12px;
}

.zone-grid-scroll {
  max-height: min(46vh, 460px);
  overflow-y: auto;
  padding-right: 4px;
}

.zone-mini-card {
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  height: 54px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.zone-mini-card:hover {
  border-color: rgba(8, 145, 178, 0.45);
  box-shadow: 0 6px 16px rgba(8, 145, 178, 0.10);
  transform: translateY(-2px);
}

.zone-mini-card.active {
  border-color: #0891b2;
  background: linear-gradient(135deg, #ecfeff 0%, #f0f9ff 100%);
  box-shadow: 0 6px 18px rgba(8, 145, 178, 0.16);
}

.zone-mini-card.selected {
  outline: 2px solid rgba(8, 145, 178, 0.35);
  outline-offset: -2px;
}

.zmc-header {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  min-height: 28px;
}

.zmc-num {
  font-size: 12px;
  font-weight: 700;
  color: #0891b2;
  flex: 0 0 24px;
}

.zmc-nickname {
  flex: 1 1 auto;
  min-width: 0;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.zmc-area {
  flex: 0 0 auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
}

.zmc-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  flex: 0 0 auto;
}

@media (max-width: 640px) {
  .zone-table-card {
    margin-bottom: 10px;
  }

  .zone-table-card :deep(.el-card__body) {
    padding: 8px;
  }

  .building-view,
  .building-view :deep(button),
  .building-view :deep(.el-button),
  .building-view :deep(.el-checkbox__input),
  .zone-mini-card,
  .hour-cell,
  .setpoint-weekday-pill {
    -webkit-tap-highlight-color: var(--bv-tap-highlight);
    touch-action: manipulation;
  }

  .zone-grid {
    gap: 8px;
  }

  .zone-grid-toolbar {
    gap: 8px;
    padding: 2px 0 6px;
    margin-bottom: 0;
  }

  .zone-grid-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .zone-grid-scroll {
    max-height: 38vh;
    padding-right: 2px;
  }

  .zone-mini-card {
    height: 44px;
    padding: 6px 7px;
    border-radius: 8px;
  }

  .zmc-header {
    min-height: 30px;
    gap: 4px;
  }

  .zmc-num {
    flex-basis: auto;
    font-size: 11px;
  }

  .zmc-area {
    padding: 1px 5px;
    font-size: 10px;
  }

  .zmc-nickname {
    font-size: 11px;
  }

  .zone-grid:not(.is-zone-select-mode) .zmc-nickname {
    display: none;
  }

  .zmc-actions {
    gap: 0;
  }

  .zmc-actions :deep(.el-button) {
    width: 24px;
    min-width: 24px;
    height: 24px;
    min-height: 24px;
    padding: 0;
  }

  .zone-mini-card,
  .building-mb-icon-btn,
  .building-mb-save,
  .hour-cell,
  .setpoint-weekday-pill {
    transition: transform 0.12s ease, background-color 0.12s ease, border-color 0.12s ease;
  }

  .zone-mini-card,
  .zone-mini-card:hover,
  .zone-mini-card.active,
  .zone-mini-card.active:hover {
    box-shadow: none;
    transform: none;
  }

  .zone-mini-card:hover {
    border-color: #e2e8f0;
  }

  .zone-mini-card.active,
  .zone-mini-card.active:hover {
    border-color: #0891b2;
  }

  .zone-mini-card:active {
    transform: scale(0.99);
    background: #f8fafc;
    border-color: rgba(8, 145, 178, 0.55);
  }

  .zone-mini-card.active:active {
    background: #e0f7fb;
  }

  .building-mb-icon-btn:active,
  .building-mb-save:active,
  .hour-cell:active,
  .setpoint-weekday-pill:active,
  .building-view :deep(.el-button:active) {
    transform: scale(var(--bv-button-press-scale));
  }

  .building-view :deep(.bv-action-btn),
  .building-view :deep(.bv-action-btn:hover),
  .building-view :deep(.bv-action-btn:focus),
  .building-view :deep(.bv-action-btn:focus-visible),
  .building-view :deep(.bv-action-btn:active) {
    --el-button-hover-bg-color: transparent;
    --el-button-active-bg-color: transparent;
    --el-button-hover-border-color: transparent;
    --el-button-active-border-color: transparent;
    --el-button-outline-color: transparent;
    background: transparent !important;
    border-color: transparent !important;
    box-shadow: var(--bv-button-shadow) !important;
    -webkit-box-shadow: var(--bv-button-shadow) !important;
    outline: none !important;
  }

  .building-view :deep(.bv-action-btn:active) {
    transform: scale(var(--bv-icon-button-press-scale));
  }

  .building-view :deep(button:focus:not(:focus-visible)),
  .building-view :deep(.el-button:focus:not(:focus-visible)) {
    outline: none;
    box-shadow: none;
  }
}

:deep(.el-table .el-input-number) {
  width: 100%;
}

.zone-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-weight: 600;
}

.zone-detail-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.zone-detail-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.zone-nickname-item {
  margin-bottom: 0;
}

.zone-nickname-item :deep(.el-input) {
  max-width: none;
}

.zone-inline-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.zone-inline-item :deep(.el-form-item__label) {
  flex: 0 0 auto;
  width: auto !important;
  min-width: 28px;
  margin: 0 !important;
  padding: 0 !important;
  line-height: 32px;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.zone-inline-item :deep(.el-form-item__content) {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0 !important;
}

.zone-basic-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-bottom: 8px;
}

.zone-basic-field {
  flex: 1 1 210px;
  min-width: 180px;
}

.zone-basic-number,
.zone-basic-select {
  width: 100%;
}

/* ---- Zone card ---- */
.zone-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.zone-card :deep(.el-card__header) {
  padding: 14px 18px;
  background: #f8fafc;
}

.zone-card :deep(.el-card__body) {
  padding: 12px 14px 14px;
}

.zone-form {
  padding: 4px 0;
}

@media (max-width: 640px) {
  .zone-card :deep(.el-card__body) {
    padding: 10px;
  }

  .zone-basic-row {
    gap: 6px 10px;
  }

  .zone-basic-field {
    flex: 1 1 calc(50% - 5px);
    min-width: 0;
  }

  .zone-inline-item {
    gap: 4px;
    margin-bottom: 6px;
  }

  .zone-inline-item :deep(.el-form-item__label) {
    min-width: 24px;
    font-size: 12px;
  }
}

:deep(.zone-card .el-divider__text) {
  background: rgb(250, 252, 253);
}

/* ---- Internal gains (new bar-chart layout) ---- */
.ig-param {
  margin-bottom: 16px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.ig-param-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.ig-param-label {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
  flex: 0 0 34px;
}

.ig-inline-controls {
  flex: 1 1 260px;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.ig-unit-input {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.ig-unit-text,
.ig-multiply {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.ig-schedule-button {
  margin-left: auto;
}

.ig-peak {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #ecfeff;
  border: 1px solid #a5f3fc;
  border-radius: 6px;
}

.ig-peak-label {
  font-size: 12px;
  color: #0e7490;
  font-weight: 600;
  white-space: nowrap;
}

.ig-number {
  width: 96px;
  flex: 0 0 96px;
}

.ig-number--heat {
  width: 82px;
  flex-basis: 82px;
}

.ig-schedules {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 640px) {
  .ig-param-header {
    flex-direction: row;
    align-items: center;
    gap: 6px;
  }

  .ig-param-label {
    flex: 0 0 34px;
  }

  .ig-param {
    padding: 0;
  }

  .ig-peak {
    flex: 1 1 calc(50% - 4px);
    justify-content: space-between;
    gap: 4px;
    padding: 4px 6px;
    min-width: 0;
  }

  .ig-peak-label {
    font-size: 11px;
  }

  .ig-number {
    width: 66px;
    flex-basis: 66px;
  }

  .ig-number--heat {
    width: 62px;
    flex-basis: 62px;
  }

  .ig-inline-controls {
    flex: 1 1 150px;
    gap: 4px;
  }

  .ig-unit-text,
  .ig-multiply {
    font-size: 11px;
  }

  .ig-schedule-button {
    padding: 5px 8px;
  }
}

/* ---- Legacy setpoint param-row ---- */
.param-row {
  margin-bottom: 16px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.param-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: 8px;
}

.param-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

/* ---- Schedule ---- */
.param-schedules {
  padding-left: 0;
}

.schedule-group {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  background: var(--el-fill-color-lighter);
  position: relative;
}

.schedule-group.schedule-conflict {
  border-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.setpoint-schedules {
  padding-left: 0;
}

.setpoint-param-header {
  margin-bottom: 8px;
}

.setpoint-schedule-card {
  background: #ffffff;
  border-color: #e4e4e7;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.setpoint-schedule-card:hover {
  border-color: rgba(8, 145, 178, 0.35);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.setpoint-schedule-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.setpoint-schedule-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.setpoint-type-badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(14, 165, 233, 0.12);
  color: #0284c7;
}

.setpoint-schedule-title {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setpoint-name-input {
  width: 100%;
  background: transparent;
  border: 0;
  border-bottom: 1px solid transparent;
  outline: none;
  color: #18181b;
  font-size: 14px;
  font-weight: 700;
  padding: 2px 0;
}

.setpoint-name-input:focus {
  border-bottom-color: #0891b2;
}

.setpoint-name-input::placeholder {
  color: #a1a1aa;
}

.setpoint-type-tag {
  font-size: 11px;
  color: #a1a1aa;
  font-weight: 500;
}

.setpoint-schedule-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  min-width: 0;
}

.setpoint-del-btn {
  background: transparent;
  border: 1px solid #e4e4e7;
  color: #a1a1aa;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}

.setpoint-del-btn:hover {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.4);
  color: #ef4444;
}

.setpoint-value-settings {
  display: flex;
  align-items: center;
  gap: 16px 32px;
  flex-wrap: wrap;
}

.setpoint-value-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.setpoint-value-input {
  width: 92px;
  flex: 0 0 92px;
}

.setpoint-value-input :deep(.el-input__wrapper) {
  min-height: 30px;
  background: #fafafa;
  border: 1px solid #e4e4e7;
  box-shadow: none;
}

.setpoint-meta-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 32px;
  align-items: center;
}

.setpoint-meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.setpoint-meta-label {
  flex: 0 0 auto;
  width: auto;
  color: #71717a;
  font-weight: 500;
}

.setpoint-date-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.setpoint-month-select {
  width: 82px;
}

.setpoint-day-select {
  width: 70px;
}

.setpoint-weekday-pills {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.setpoint-weekday-pill {
  width: 32px;
  height: 30px;
  padding: 0;
  background: #fafafa;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  color: #71717a;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.setpoint-weekday-pill.is-active {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.28);
  color: #2563eb;
  font-weight: 600;
}

.setpoint-time-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.setpoint-hours-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.setpoint-hours-quick {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.setpoint-hour-grid {
  display: grid;
  grid-template-columns: repeat(24, minmax(0, 1fr));
  gap: 3px;
  height: 24px;
}

.setpoint-hour-cell {
  width: auto;
  height: 24px;
  border: 0;
  border-radius: 3px;
  background: #f4f4f5;
  color: transparent;
  font-size: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.setpoint-hour-cell:hover {
  background: rgba(148, 163, 184, 0.25);
}

.setpoint-hour-cell.active {
  background: #0891b2;
  border-color: #0891b2;
}

.setpoint-hour-ticks {
  grid-column: 2;
  display: grid;
  grid-template-columns: repeat(24, minmax(0, 1fr));
  gap: 4px;
  color: #a1a1aa;
  font-size: 10px;
  line-height: 14px;
}

.setpoint-hour-ticks span {
  white-space: nowrap;
}

.conflict-badge {
  position: absolute;
  top: -10px;
  right: 12px;
}

.schedule-group-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.schedule-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.schedule-sub-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.schedule-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.schedule-sep {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin: 0 2px;
}

.day-checkboxes {
  flex-wrap: wrap;
}

/* ---- Hour grid ---- */
.schedule-hours-line {
  flex-direction: column;
  align-items: flex-start;
}

.hours-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
  width: 100%;
}

.hours-quick {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.hour-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.hour-cell {
  width: 32px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
  background: var(--el-fill-color-blank);
  color: var(--el-text-color-regular);
  transition: all 0.15s;
}

.hour-cell:hover {
  border-color: var(--el-color-primary-light-3);
}

.hour-cell.active {
  background: var(--el-color-primary);
  color: #fff;
  border-color: var(--el-color-primary);
}

.hour-grid.setpoint-hour-grid {
  display: grid;
  grid-template-columns: repeat(24, minmax(0, 1fr));
  gap: 3px;
  height: 24px;
}

.hour-cell.setpoint-hour-cell {
  width: auto;
  height: 24px;
  border: 0;
  border-radius: 3px;
  background: #f4f4f5;
  color: transparent;
  font-size: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.schedule-note {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 6px;
}

/* ---- Zone position & wall config ---- */
.zone-position-row {
  margin-bottom: 8px;
}

.wall-config-group {
  display: flex;
  gap: 0 14px;
  flex-wrap: wrap;
}

.wall-config-group :deep(.el-checkbox) {
  height: 28px;
  margin-right: 0;
}

.wall-config-group :deep(.el-checkbox__label) {
  padding-left: 5px;
}

.wall-config-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.wall-config-item :deep(.el-form-item__label) {
  flex: 0 0 auto;
  width: auto !important;
  margin: 0 !important;
  padding: 0 !important;
  line-height: 32px;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.wall-config-item :deep(.el-form-item__content) {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0 !important;
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .building-view {
    padding: 0 8px;
  }

  .wall-config-item {
    gap: 6px;
    margin-bottom: 6px;
  }

  .wall-config-group {
    gap: 0 8px;
  }

  .wall-config-group :deep(.el-checkbox) {
    height: 24px;
  }

  .wall-config-group :deep(.el-checkbox__label) {
    padding-left: 3px;
    font-size: 12px;
  }

  .page-header {
    display: none;
  }

  .zone-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .zone-selector {
    width: 100%;
  }

  .param-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .schedule-group-top {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .schedule-line {
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }

  .schedule-line .schedule-sub-label {
    width: 100%;
    margin-bottom: 2px;
  }

  .schedule-line .el-select {
    width: 70px !important;
  }

  .schedule-sep {
    margin: 0;
  }

  .setpoint-schedule-card {
    padding: 14px;
    gap: 12px;
  }

  .setpoint-schedule-head {
    align-items: flex-start;
    gap: 8px;
    flex-wrap: nowrap;
  }

  .setpoint-schedule-left {
    gap: 8px;
    min-width: 0;
  }

  .setpoint-type-badge {
    width: 32px;
    height: 32px;
    border-radius: 8px;
  }

  .setpoint-schedule-title {
    flex: 0 0 70px;
    width: 70px;
  }

  .setpoint-type-tag {
    display: none;
  }

  .setpoint-schedule-actions {
    flex: 1;
    justify-content: flex-end;
  }

  .setpoint-value-settings {
    gap: 8px;
  }

  .setpoint-value-row {
    gap: 4px;
  }

  .setpoint-time-row {
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 8px;
  }

  .setpoint-hours-header {
    align-items: flex-start;
  }

  .setpoint-hour-ticks {
    gap: 3px;
    font-size: 9px;
  }

  .hour-grid.setpoint-hour-grid {
    grid-template-columns: repeat(24, minmax(0, 1fr));
    gap: 3px;
    height: 24px;
  }

  .hour-cell.setpoint-hour-cell {
    width: auto;
    height: 24px;
    font-size: 0;
  }

  .setpoint-meta-row {
    width: 100%;
    gap: 8px;
  }

  .setpoint-meta-label {
    width: 34px !important;
    flex: 0 0 34px;
    margin-bottom: 0 !important;
  }

  .setpoint-date-controls {
    flex: 1;
    flex-wrap: nowrap;
  }

  .setpoint-month-select {
    width: 68px !important;
  }

  .setpoint-day-select {
    width: 60px !important;
  }

  .setpoint-weekday-pills {
    flex: 1;
    gap: 4px;
  }

  .setpoint-weekday-pill {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    font-size: 12px;
  }

  .hour-cell {
    width: 28px;
    height: 26px;
    font-size: 11px;
  }

  .hours-quick .el-button {
    padding: 2px 4px;
    font-size: 12px;
  }

  .day-checkboxes :deep(.el-checkbox-button__inner) {
    padding: 4px 8px;
    font-size: 12px;
  }

  .zone-table-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .zone-table-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    width: 100%;
  }

  .zone-table-actions .el-button {
    flex: 1;
    min-width: 0;
  }

  .mobile-zone-area {
    display: block;
    font-size: 11px;
    color: #94a3b8;
    margin-top: 2px;
  }

  .mobile-ops {
    display: flex;
    flex-direction: column;
    gap: 2px;
    align-items: flex-start;
  }

  .mobile-ops .el-button {
    margin-left: 0 !important;
    padding: 2px 0;
  }
}

.building-mobile-topbar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: transparent;
  border: none;
  min-height: 44px;
  flex-shrink: 0;
}

.building-mb-left {
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.building-mb-back {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-body, #1e293b);
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
}

.building-mb-back:active {
  background: rgba(15, 23, 42, 0.06);
}

.building-mb-area {
  max-width: 66px;
  padding: 3px 6px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.18);
  color: #047857;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.building-mb-title {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  max-width: calc(100% - 230px);
  min-width: 0;
  text-align: center;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.building-mb-actions {
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.building-mb-icon-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.86);
  color: #2563eb;
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
  -webkit-tap-highlight-color: transparent;
}

.building-mb-icon-btn--danger {
  color: #dc2626;
  border-color: rgba(220, 38, 38, 0.18);
}

.building-mb-icon-btn:disabled {
  opacity: 0.42;
  color: #94a3b8;
  border-color: rgba(148, 163, 184, 0.22);
  box-shadow: none;
}

.building-mb-save-badge {
  flex: 0 0 auto;
}

.building-mb-save {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.42);
  border-radius: 10px;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.24);
}

.building-mb-save:disabled {
  opacity: 0.6;
  box-shadow: none;
}

.building-mb-save .is-loading {
  animation: building-spin 1s linear infinite;
}

@keyframes building-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
