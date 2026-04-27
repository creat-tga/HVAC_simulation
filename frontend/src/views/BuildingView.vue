<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick, watch } from 'vue'
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
}

function removeScheduleAt(param: ParamConfig, idx: number) {
  param.schedules.splice(idx, 1)
  if (param.schedules.length === 0) {
    // Always keep at least one — re-add a default
    param.schedules.push(createOfficeRatiosSchedule(t('building.schedule.presetWeekday')))
  }
}

function addDayGroup(param: ParamConfig) {
  if (param.schedules.length >= MAX_SCHEDULES) {
    ElMessage.warning(t('building.schedule.maxGroupsHint', { max: MAX_SCHEDULES }))
    return
  }
  param.schedules.push(createSchedule(param.fixed_value))
}

function removeDayGroup(param: ParamConfig, idx: number) {
  param.schedules.splice(idx, 1)
  if (param.schedules.length === 0) param.mode = 'fixed'
}

function presetWeekday(param: ParamConfig) {
  param.schedules = [
    createSchedule(param.fixed_value, t('building.schedule.presetWeekday'), [1, 2, 3, 4, 5], [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]),
    createSchedule(param.fixed_value * 0.3, t('building.schedule.presetWeekend'), [6, 7], [10, 11, 12, 13, 14, 15]),
  ]
}

function switchMode(param: ParamConfig, mode: string | number | boolean | undefined) {
  const m = String(mode) as 'fixed' | 'scheduled'
  param.mode = m
  if (m === 'scheduled' && param.schedules.length === 0) {
    presetWeekday(param)
  }
}

// Quick hour range toggle
function toggleHourRange(sch: DaySchedule, start: number, end: number) {
  const range = Array.from({ length: end - start }, (_, i) => start + i)
  const allSelected = range.every(h => sch.hours.includes(h))
  if (allSelected) {
    sch.hours = sch.hours.filter(h => h < start || h >= end)
  } else {
    const set = new Set(sch.hours)
    range.forEach(h => set.add(h))
    sch.hours = Array.from(set).sort((a, b) => a - b)
  }
}

function selectAllHours(sch: DaySchedule) {
  sch.hours = Array.from({ length: 24 }, (_, i) => i)
}

function clearAllHours(sch: DaySchedule) {
  sch.hours = []
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

watch(editZones, () => {
  if (_conflictTimer) clearTimeout(_conflictTimer)
  _conflictTimer = setTimeout(_checkConflicts, 500)
}, { deep: true })

// ----- Unsaved changes detection (version-based) -----
const editVersion = ref(0)
const savedVersion = ref(0)
const _initializing = ref(true)
const isDirty = computed(() => editVersion.value !== savedVersion.value)

function markDirty() {
  if (_initializing.value) return
  editVersion.value++
}

// Use deep watcher only to bump version counter (cheap operation)
let _dirtyTimer: ReturnType<typeof setTimeout> | null = null
watch(editZones, () => {
  if (_dirtyTimer) clearTimeout(_dirtyTimer)
  _dirtyTimer = setTimeout(markDirty, 500)
}, { deep: true })

// ----- Zone table pagination -----
const pageSize = ref(30)
const currentPage = ref(1)

const totalZones = computed(() => editZones.value.length)

const pagedZones = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return editZones.value.slice(start, start + pageSize.value)
})

function handlePageChange(page: number) {
  currentPage.value = page
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
}

// Ensure currentPage stays valid when zones are deleted
watch(totalZones, (total) => {
  const maxPage = Math.max(1, Math.ceil(total / pageSize.value))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})

// ----- Zone management -----
const MAX_ZONES = 999 // 最大分区数
const activeZone = computed(() => editZones.value[selectedZoneIdx.value] ?? null)

function nextZoneNumber(): number {
  const prefix = t('building.zone.defaultPrefix')
  let max = 0
  for (const z of editZones.value) {
    if (z.name.startsWith(prefix)) {
      const n = parseInt(z.name.slice(prefix.length).trim(), 10)
      if (!isNaN(n) && n > max) max = n
    }
  }
  return max + 1
}

// ----- Table selection for batch operations -----
const selectedRows = ref<BuildingZone[]>([])
const batchAddVisible = ref(false)
const batchAddCount = ref(3)
const batchAddName = ref('')

function isZoneSelected(zone: BuildingZone): boolean {
  return selectedRows.value.includes(zone)
}

function toggleZoneSelect(zone: BuildingZone, checked: any) {
  if (checked) {
    if (!selectedRows.value.includes(zone)) selectedRows.value.push(zone)
  } else {
    selectedRows.value = selectedRows.value.filter(z => z !== zone)
  }
}

const allPagedSelected = computed(() => {
  return pagedZones.value.length > 0 && pagedZones.value.every(z => selectedRows.value.includes(z))
})

const someSelected = computed(() =>
  selectedRows.value.length > 0 && !allPagedSelected.value
)

function toggleAllPaged(checked: any) {
  if (checked) {
    const set = new Set(selectedRows.value)
    pagedZones.value.forEach(z => set.add(z))
    selectedRows.value = Array.from(set)
  } else {
    const pset = new Set(pagedZones.value)
    selectedRows.value = selectedRows.value.filter(z => !pset.has(z))
  }
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
  const name = `${t('building.zone.defaultPrefix')}${nextZoneNumber()}`
  editZones.value.push(createDefaultZone(name))
  nextTick(() => {
    selectedZoneIdx.value = editZones.value.length - 1
    activePresetKey.value = ''
    // Jump to last page to show the new zone
    currentPage.value = Math.ceil(editZones.value.length / pageSize.value)
  })
}

function copyZone(zone: BuildingZone) {
  if (editZones.value.length >= MAX_ZONES) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  const copy: BuildingZone = JSON.parse(JSON.stringify(zone))
  copy.name = copy.name ? `${copy.name} (${t('building.zone.copy')})` : ''
  editZones.value.push(copy)
  nextTick(() => {
    selectedZoneIdx.value = editZones.value.length - 1
    currentPage.value = Math.ceil(editZones.value.length / pageSize.value)
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
  if (selectedZoneIdx.value >= editZones.value.length) {
    selectedZoneIdx.value = editZones.value.length - 1
  }
}

async function batchDelete() {
  if (selectedRows.value.length === 0) return
  if (selectedRows.value.length >= editZones.value.length) {
    ElMessage.warning(t('building.zone.lastZoneHint'))
    return
  }
  await ElMessageBox.confirm(
    t('building.zone.batchDeleteConfirm', { count: selectedRows.value.length }),
    t('common.warning'), { type: 'warning' }
  )
  const toRemove = new Set(selectedRows.value)
  editZones.value = editZones.value.filter(z => !toRemove.has(z))
  selectedZoneIdx.value = Math.min(selectedZoneIdx.value, editZones.value.length - 1)
  selectedRows.value = []
}

function batchCopy() {
  if (selectedRows.value.length === 0) return
  const remaining = MAX_ZONES - editZones.value.length
  if (remaining <= 0) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  const toCopy = selectedRows.value.slice(0, remaining)
  const copies = toCopy.map(z => {
    const copy: BuildingZone = JSON.parse(JSON.stringify(z))
    copy.name = copy.name ? `${copy.name} (${t('building.zone.copy')})` : ''
    return copy
  })
  editZones.value.push(...copies)
  // Jump to last page to show copied zones
  currentPage.value = Math.ceil(editZones.value.length / pageSize.value)
  ElMessage.success(t('building.zone.batchCopySuccess', { count: copies.length }))
}

function confirmBatchAdd() {
  const remaining = MAX_ZONES - editZones.value.length
  if (remaining <= 0) {
    ElMessage.warning(t('building.zone.maxZonesHint', { max: MAX_ZONES }))
    return
  }
  const count = Math.max(1, Math.min(batchAddCount.value, 200, remaining))
  const prefix = batchAddName.value || t('building.zone.defaultPrefix')
  let num = 1
  if (!batchAddName.value) {
    num = nextZoneNumber()
  }
  for (let i = 0; i < count; i++) {
    const name = batchAddName.value
      ? `${batchAddName.value} ${editZones.value.length + 1}`
      : `${prefix}${num + i}`
    editZones.value.push(createDefaultZone(name))
  }
  batchAddVisible.value = false
  // Jump to last page to show newly added zones
  currentPage.value = Math.ceil(editZones.value.length / pageSize.value)
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
    name: raw.name || '',
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
      name: t('building.zone.presets.office'),
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
  nextTick(() => {
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
    if (_dirtyTimer) { clearTimeout(_dirtyTimer); _dirtyTimer = null }
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
})

// ----- Constants -----
const ALL_HOURS = Array.from({ length: 24 }, (_, i) => i)
const MONTH_DAYS: Record<number, number> = { 1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31 }
</script>

<template>
  <div class="building-view" v-if="building">
    <Teleport v-if="isMobile" to="#ws-mobile-topbar-slot" defer>
      <div class="building-mobile-topbar">
        <button class="building-mb-back" :aria-label="t('workspace.backToProjects') || '返回'" @click="goBackToList">
          <el-icon :size="20">
            <ArrowLeft />
          </el-icon>
        </button>
        <div class="building-mb-spacer" />
        <el-tag type="success" effect="plain" size="small" class="building-mb-area">{{ totalArea.toFixed(1) }}
          m²</el-tag>
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
      <template #header>
        <div class="zone-table-header">
          <span class="zone-table-title">{{ t('building.zone.title') }} ({{ editZones.length }})</span>
          <div class="zone-table-actions">
            <el-button type="primary" :icon="Plus" size="small" @click="addZone">
              <span v-if="!isMobile">{{ t('building.zone.add') }}</span>
            </el-button>
            <el-button :icon="FolderAdd" size="small" @click="batchAddVisible = true">
              <span v-if="!isMobile">{{ t('building.zone.batchAdd') }}</span>
            </el-button>
            <el-button :icon="CopyDocument" size="small" :disabled="selectedRows.length === 0" @click="batchCopy">
              <span v-if="!isMobile">{{ t('building.zone.batchCopy') }}</span>
            </el-button>
            <el-button type="danger" :icon="Delete" size="small" plain :disabled="selectedRows.length === 0"
              @click="batchDelete">
              <span v-if="!isMobile">{{ t('building.zone.batchDelete') }}</span>
            </el-button>
          </div>
        </div>
      </template>

      <div class="zone-grid">
        <div class="zone-grid-toolbar">
          <el-checkbox :model-value="allPagedSelected" :indeterminate="someSelected"
            @change="(v: any) => toggleAllPaged(v)">
            {{ t('common.selectAll') }}
            <span v-if="selectedRows.length > 0" class="zg-sel-count">({{ selectedRows.length }})</span>
          </el-checkbox>
        </div>
        <div class="zone-grid-list">
          <div v-for="(zone, idx) in pagedZones" :key="editZones.indexOf(zone)" class="zone-mini-card"
            :class="{ active: editZones.indexOf(zone) === selectedZoneIdx, selected: isZoneSelected(zone) }"
            @click="handleRowClick(zone)">
            <div class="zmc-header" @click.stop>
              <el-checkbox :model-value="isZoneSelected(zone)" @change="(v: any) => toggleZoneSelect(zone, v)" />
              <span class="zmc-num">#{{ (currentPage - 1) * pageSize + idx + 1 }}</span>
              <el-input v-model="zone.name" size="small" class="zmc-name"
                :placeholder="t('building.zone.pleaseInputName')" />
              <div class="zmc-actions">
                <el-button text circle type="primary" size="small" :icon="CopyDocument" :title="t('building.zone.copy')"
                  @click="copyZone(zone)" />
                <el-button text circle type="danger" size="small" :icon="Delete" :disabled="editZones.length <= 1"
                  :title="t('building.zone.delete')" @click="removeZone(zone)" />
              </div>
            </div>
            <div class="zmc-body" @click.stop>
              <div class="zmc-field">
                <label>{{ t('building.zone.area') }}</label>
                <el-input-number v-model="zone.area" :min="0.1" :max="9999.9" :precision="1" size="small"
                  :controls="false" class="zmc-number" />
              </div>
              <div class="zmc-field">
                <label>{{ t('building.zone.floorHeight') }}</label>
                <el-input-number v-model="zone.floor_height" :min="1" :max="100" :precision="1" size="small"
                  :controls="false" class="zmc-number" />
              </div>
              <div class="zmc-field zmc-field--full">
                <label>{{ t('building.envelope.zonePosition') }}</label>
                <el-select v-model="zone.zone_position" size="small" class="zmc-select">
                  <el-option value="single" :label="t('building.envelope.position.single')" />
                  <el-option value="top" :label="t('building.envelope.position.top')" />
                  <el-option value="middle" :label="t('building.envelope.position.middle')" />
                  <el-option value="bottom" :label="t('building.envelope.position.bottom')" />
                </el-select>
              </div>
            </div>
          </div>
        </div>
      </div>
      <el-pagination v-if="totalZones > 30" v-model:current-page="currentPage" v-model:page-size="pageSize"
        :page-sizes="[20, 30, 50, 100]" :total="totalZones" layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 12px; justify-content: flex-end" @size-change="handleSizeChange"
        @current-change="handlePageChange" />
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
          <span>{{ activeZone.name || t('building.zone.title') + ' ' + (selectedZoneIdx + 1) }} — {{
            t('building.zone.detailEdit') }}</span>
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
      </template>
      <el-form label-position="top" class="zone-form">

        <!-- Envelope -->
        <el-divider content-position="left">{{ t('building.envelope.title') }}</el-divider>

        <!-- Wall exterior config -->
        <el-row :gutter="16">
          <el-col :xs="24" :sm="24">
            <el-form-item :label="t('building.envelope.wallType')">
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

        <!-- Internal Gains (bar-chart schedule editor) -->
        <el-divider content-position="left">{{ t('building.internalGains.title') }}</el-divider>

        <div v-for="pm in PARAM_METAS" :key="pm.key" class="ig-param">
          <div class="ig-param-header">
            <span class="ig-param-label">{{ pm.key === 'people_density' ? t('building.internalGains.peopleShort') :
              t(pm.label) }}</span>
            <div class="ig-peak">
              <span class="ig-peak-label">{{ t('building.schedule.editor.peakValue') }} ({{ paramUnit(pm.key) }})</span>
              <el-input-number v-model="getParam(activeZone, pm.key).fixed_value" :min="pm.min" :max="pm.max"
                :precision="pm.precision" :step="pm.step" :controls="false" size="small" class="ig-number" />
            </div>
            <!-- 人员散热量（仅在 people_density 时显示） -->
            <div v-if="pm.key === 'people_density'" class="ig-peak">
              <span class="ig-peak-label">散热量 (W/人)</span>
              <el-input-number v-model="activeZone.people_heat_gain" :min="0" :max="500" :precision="0" :step="1"
                :controls="false" size="small" class="ig-number ig-number--heat" />
            </div>
            <el-button type="primary" plain size="small" :icon="Plus"
              :disabled="getParam(activeZone, pm.key).schedules.length >= MAX_SCHEDULES"
              @click="addScheduleForParam(getParam(activeZone, pm.key))">
              {{ t('building.schedule.editor.addSchedule') }}
              ({{ getParam(activeZone, pm.key).schedules.length }}/{{ MAX_SCHEDULES }})
            </el-button>
          </div>
          <div class="ig-schedules">
            <ScheduleEditor v-for="(sch, sIdx) in getParam(activeZone, pm.key).schedules" :key="sIdx" :model-value="sch"
              :peak-value="getParam(activeZone, pm.key).fixed_value" :unit="paramUnit(pm.key)" :type="paramType(pm.key)"
              :param-label="t(pm.label)" :removable="getParam(activeZone, pm.key).schedules.length > 1"
              :conflict-message="getInternalScheduleConflictMsg(getParam(activeZone, pm.key).schedules, sIdx)"
              @update:model-value="(v: DaySchedule) => getParam(activeZone, pm.key).schedules[sIdx] = v"
              @remove="removeScheduleAt(getParam(activeZone, pm.key), sIdx)" />
          </div>
        </div>

        <!-- Setpoints -->
        <el-divider content-position="left">{{ t('building.setpoint.title') }}</el-divider>

        <div v-for="pm in SETPOINT_METAS" :key="pm.key" class="param-row">
          <div class="param-header">
            <span class="param-label">{{ t(pm.label) }}</span>
            <el-radio-group :model-value="getParam(activeZone, pm.key).mode"
              @update:model-value="(v: string | number | boolean | undefined) => switchMode(getParam(activeZone, pm.key), v)"
              size="small">
              <el-radio-button value="fixed">{{ t('building.schedule.fixed') }}</el-radio-button>
              <el-radio-button value="scheduled">{{ t('building.schedule.scheduled') }}</el-radio-button>
            </el-radio-group>
          </div>

          <!-- Fixed mode -->
          <div v-if="getParam(activeZone, pm.key).mode === 'fixed'" class="param-fixed">
            <el-input-number v-model="getParam(activeZone, pm.key).fixed_value" :min="pm.min" :max="pm.max"
              :precision="pm.precision" :step="pm.step" />
          </div>

          <!-- Scheduled mode -->
          <div v-else class="param-schedules">
            <div v-for="(sch, sIdx) in getParam(activeZone, pm.key).schedules" :key="sIdx" class="schedule-group"
              :class="{ 'schedule-conflict': isScheduleInConflict(getParam(activeZone, pm.key).schedules, sIdx) }">
              <el-tag v-if="isScheduleInConflict(getParam(activeZone, pm.key).schedules, sIdx)" type="danger"
                size="small" effect="dark" class="conflict-badge">
                {{ t('building.schedule.conflictWarning') }}
              </el-tag>
              <div class="schedule-group-top">
                <el-input v-model="sch.name" size="small" :placeholder="t('building.schedule.dayGroupName')"
                  style="width: 140px" />
                <div class="schedule-value-row">
                  <span class="schedule-sub-label">{{ t('building.schedule.value') }}:</span>
                  <el-input-number v-model="sch.value" :min="pm.min" :max="pm.max" :precision="pm.precision"
                    :step="pm.step" size="small" style="width: 140px" />
                </div>
                <el-button type="danger" link size="small" @click="removeDayGroup(getParam(activeZone, pm.key), sIdx)">
                  {{ t('building.schedule.removeSlot') }}
                </el-button>
              </div>
              <div class="schedule-line">
                <span class="schedule-sub-label">{{ t('building.schedule.dateRange') }}:</span>
                <el-select v-model="sch.start_month" size="small" style="width: 80px">
                  <el-option v-for="m in 12" :key="m" :label="t(`building.schedule.monthNames.${m}`)" :value="m" />
                </el-select>
                <el-select v-model="sch.start_day" size="small" style="width: 70px">
                  <el-option v-for="d in (MONTH_DAYS[sch.start_month] || 31)" :key="d"
                    :label="`${d}${t('building.schedule.dayUnit')}`" :value="d" />
                </el-select>
                <span class="schedule-sep">~</span>
                <el-select v-model="sch.end_month" size="small" style="width: 80px">
                  <el-option v-for="m in 12" :key="m" :label="t(`building.schedule.monthNames.${m}`)" :value="m" />
                </el-select>
                <el-select v-model="sch.end_day" size="small" style="width: 70px">
                  <el-option v-for="d in (MONTH_DAYS[sch.end_month] || 31)" :key="d"
                    :label="`${d}${t('building.schedule.dayUnit')}`" :value="d" />
                </el-select>
              </div>
              <div class="schedule-line">
                <span class="schedule-sub-label">{{ t('building.schedule.weekdays') }}:</span>
                <el-checkbox-group v-model="sch.days" size="small" class="day-checkboxes">
                  <el-checkbox-button v-for="d in [1, 2, 3, 4, 5, 6, 7]" :key="d" :value="d">
                    {{ t(`building.schedule.dayNames.${d}`) }}
                  </el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div class="schedule-line schedule-hours-line">
                <div class="hours-header">
                  <span class="schedule-sub-label">{{ t('building.schedule.hours') }}:</span>
                  <div class="hours-quick">
                    <el-button link type="primary" size="small" @click="selectAllHours(sch)">{{
                      t('building.schedule.selectAll') }}</el-button>
                    <el-button link type="primary" size="small" @click="clearAllHours(sch)">{{
                      t('building.schedule.clearAll') }}</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 8, 18)">8~18</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 0, 8)">0~8</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 18, 24)">18~24</el-button>
                  </div>
                </div>
                <div class="hour-grid">
                  <label v-for="h in ALL_HOURS" :key="h" class="hour-cell" :class="{ active: sch.hours.includes(h) }"
                    @click="sch.hours.includes(h) ? (sch.hours = sch.hours.filter(x => x !== h)) : sch.hours.push(h)">
                    {{ h }}
                  </label>
                </div>
              </div>
            </div>
            <el-button type="primary" plain size="small" @click="addDayGroup(getParam(activeZone, pm.key))"
              :disabled="getParam(activeZone, pm.key).schedules.length >= MAX_SCHEDULES">
              + {{ t('building.schedule.addDayGroup') }}
              ({{ getParam(activeZone, pm.key).schedules.length }}/{{ MAX_SCHEDULES }})
            </el-button>
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
  padding: 4px 2px;
  border-bottom: 1px dashed #e2e8f0;
  margin-bottom: 4px;
}

.zg-sel-count {
  margin-left: 6px;
  font-size: 12px;
  color: #0891b2;
  font-weight: 600;
}

.zone-grid-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.zone-mini-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
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
}

.zmc-num {
  font-size: 12px;
  font-weight: 700;
  color: #0891b2;
  flex: 0 0 24px;
}

.zmc-name {
  flex: 0 1 160px;
  min-width: 96px;
  max-width: 180px;
}

.zmc-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  flex: 0 0 auto;
}

.zmc-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 10px;
}

.zmc-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.zmc-field--full {
  grid-column: 1 / -1;
  justify-content: flex-start;
}

.zmc-field label {
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
  line-height: 1.25;
  white-space: nowrap;
  flex: 0 0 auto;
}

.zmc-number {
  width: 96px;
  flex: 0 0 96px;
}

.zmc-select {
  width: min(100%, 230px);
  flex: 1 1 180px;
  max-width: 230px;
}

@media (max-width: 640px) {
  .zone-grid-list {
    grid-template-columns: 1fr;
  }

  .zone-mini-card {
    padding: 10px;
  }

  .zmc-body {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px 6px;
  }

  .zmc-field {
    gap: 4px;
  }

  .zmc-field label {
    font-size: 10px;
  }

  .zmc-number {
    width: 72px;
    flex-basis: 72px;
  }

  .zmc-field--full {
    grid-column: 1 / -1;
    justify-content: space-between;
  }

  .zmc-select {
    flex-basis: 190px;
    max-width: 210px;
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
}

:deep(.zone-card .el-divider__text) {
  background: rgb(250, 252, 253);
}

/* ---- Internal gains (new bar-chart layout) ---- */
.ig-param {
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.ig-param-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.ig-param-label {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
  flex: 0 0 auto;
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
    gap: 8px;
  }

  .ig-param-label {
    flex: 0 0 100%;
  }

  .ig-param {
    padding: 4px;
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
    width: 72px;
    flex-basis: 72px;
  }

  .ig-number--heat {
    width: 64px;
    flex-basis: 64px;
  }
}

/* ---- Legacy setpoint param-row ---- */
.param-row {
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
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

.param-fixed {
  padding-left: 4px;
}

/* ---- Schedule ---- */
.param-schedules {
  padding-left: 4px;
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
  gap: 16px;
  flex-wrap: wrap;
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .building-view {
    padding: 0 8px;
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
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: transparent;
  border: none;
  min-height: 44px;
  flex-shrink: 0;
}

.building-mb-back {
  flex: 0 0 auto;
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

.building-mb-spacer {
  flex: 1 1 auto;
  min-width: 0;
}

.building-mb-area {
  flex: 0 0 auto;
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
  background: var(--brand-primary, #6366f1);
  color: #fff;
  border: none;
  border-radius: 8px;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
}

.building-mb-save:disabled {
  opacity: 0.6;
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
