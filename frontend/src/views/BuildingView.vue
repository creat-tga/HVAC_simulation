<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getBuilding, updateBuilding } from '@/api/buildings'
import type { Building, BuildingUpdate, BuildingZone, ParamConfig, DaySchedule, ZonePosition, WallConfig } from '@/types/building'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Plus, Delete, ArrowDown, CopyDocument, FolderAdd } from '@element-plus/icons-vue'
import { ZONE_PRESETS, PRESET_KEYS } from '@/data/zone-presets'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const building = ref<Building | null>(null)
const saving = ref(false)
const selectedZoneIdx = ref(0)
const editingName = ref(false)
const activePresetKey = ref('')

watch(selectedZoneIdx, () => { activePresetKey.value = '' })

// Edit state
const editName = ref('')
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

function createParamConfig(val: number): ParamConfig {
  return { mode: 'fixed', fixed_value: val, schedules: [] }
}

function createSchedule(value: number, name?: string, days?: number[], hours?: number[]): DaySchedule {
  return {
    name: name || '',
    start_month: 1, start_day: 1, end_month: 12, end_day: 31,
    days: days || [1,2,3,4,5,6,7],
    hours: hours || [8,9,10,11,12,13,14,15,16,17],
    value,
  }
}

function createDefaultZone(name?: string): BuildingZone {
  const preset = ZONE_PRESETS.office
  return {
    name: name || '',
    area: 0,
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
    createSchedule(param.fixed_value, t('building.schedule.presetWeekday'), [1,2,3,4,5], [8,9,10,11,12,13,14,15,16,17]),
    createSchedule(param.fixed_value * 0.3, t('building.schedule.presetWeekend'), [6,7], [10,11,12,13,14,15]),
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

// ----- Global conflict check (debounced for performance) -----
const hasAnyConflict = ref(false)
let _conflictTimer: ReturnType<typeof setTimeout> | null = null

function _checkConflicts() {
  for (const zone of editZones.value) {
    for (const pm of ALL_PARAM_METAS) {
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

// ----- Unsaved changes detection (debounced) -----
const savedSnapshot = ref('')

function getStateSnapshot(): string {
  return JSON.stringify({ name: editName.value, zones: editZones.value })
}

const isDirty = ref(false)
let _dirtyTimer: ReturnType<typeof setTimeout> | null = null

function _checkDirty() {
  if (!savedSnapshot.value) { isDirty.value = false; return }
  isDirty.value = getStateSnapshot() !== savedSnapshot.value
}

watch([editName, editZones], () => {
  if (_dirtyTimer) clearTimeout(_dirtyTimer)
  _dirtyTimer = setTimeout(_checkDirty, 600)
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
const activeZone = computed(() => editZones.value[selectedZoneIdx.value] ?? null)

// ----- Table selection for batch operations -----
const selectedRows = ref<BuildingZone[]>([])
const batchAddVisible = ref(false)
const batchAddCount = ref(3)
const batchAddName = ref('')

function handleSelectionChange(rows: BuildingZone[]) {
  selectedRows.value = rows
}

function handleRowClick(row: BuildingZone) {
  const idx = editZones.value.indexOf(row)
  if (idx >= 0) {
    selectedZoneIdx.value = idx
    activePresetKey.value = ''
  }
}

function addZone() {
  editZones.value.push(createDefaultZone())
  nextTick(() => {
    selectedZoneIdx.value = editZones.value.length - 1
    activePresetKey.value = ''
    // Jump to last page to show the new zone
    currentPage.value = Math.ceil(editZones.value.length / pageSize.value)
  })
}

function copyZone(zone: BuildingZone) {
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
  const copies = selectedRows.value.map(z => {
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
  const count = Math.max(1, Math.min(batchAddCount.value, 50))
  for (let i = 0; i < count; i++) {
    const name = batchAddName.value
      ? `${batchAddName.value} ${editZones.value.length + 1}`
      : ''
    editZones.value.push(createDefaultZone(name))
  }
  batchAddVisible.value = false
  // Jump to last page to show newly added zones
  currentPage.value = Math.ceil(editZones.value.length / pageSize.value)
  ElMessage.success(t('building.zone.batchAddSuccess', { count }))
}

// ----- Inline name edit -----
const nameInputRef = ref<any>(null)
function startEditName() {
  editingName.value = true
  nextTick(() => nameInputRef.value?.focus())
}
function finishEditName() {
  editingName.value = false
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
      days: raw.days || [1,2,3,4,5,6,7],
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
  editName.value = data.name
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
  nextTick(() => { savedSnapshot.value = getStateSnapshot() })
  window.addEventListener('beforeunload', handleBeforeUnload)
})

// ----- Validation -----
function validateZones(): string | null {
  for (let i = 0; i < editZones.value.length; i++) {
    const z = editZones.value[i]
    const label = z.name || `${t('building.zone.title')} ${i + 1}`
    if (!z.area || z.area < 0.1) return `${label}: ${t('building.zone.area')} ${t('building.validation.minValue', { min: 0.1 })}`
    if (!z.floor_height || z.floor_height < 1) return `${label}: ${t('building.zone.floorHeight')} ${t('building.validation.minValue', { min: 1 })}`
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
  saving.value = true
  try {
    const update: BuildingUpdate = {
      name: editName.value,
      building_type: editType.value,
      climate_zone: editClimateZone.value || undefined,
      total_area: totalArea.value,
      zones: editZones.value,
    }
    const { data } = await updateBuilding(projectId, buildingId, update)
    building.value = data
    ElMessage.success(t('building.updateSuccess'))
    savedSnapshot.value = getStateSnapshot()
  } finally {
    saving.value = false
  }
}

function goSimulation() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/load`)
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
const MONTH_DAYS: Record<number, number> = { 1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31 }
</script>

<template>
  <div class="building-view" v-if="building">
    <!-- Compact header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-name-row">
          <template v-if="editingName">
            <el-input ref="nameInputRef" v-model="editName" :maxlength="30" show-word-limit
              size="large" style="width: 280px" @blur="finishEditName" @keyup.enter="finishEditName" />
          </template>
          <template v-else>
            <h1 @click="startEditName">{{ editName || building.name }}</h1>
            <el-icon class="edit-icon" @click="startEditName"><Edit /></el-icon>
          </template>
          <el-tag type="success" effect="plain" size="large" class="area-tag">{{ totalArea.toFixed(1) }} m²</el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="saving" :disabled="hasAnyConflict" @click="handleSave">{{ t('common.save') }}</el-button>
        <el-button type="success" @click="goSimulation">{{ t('nav.loadCalc') }} →</el-button>
      </div>
    </div>

    <!-- Zone table + batch toolbar -->
    <el-card class="zone-table-card" shadow="never">
      <template #header>
        <div class="zone-table-header">
          <span class="zone-table-title">{{ t('building.zone.title') }} ({{ editZones.length }})</span>
          <div class="zone-table-actions">
            <el-button type="primary" :icon="Plus" size="small" @click="addZone">{{ t('building.zone.add') }}</el-button>
            <el-button :icon="FolderAdd" size="small" @click="batchAddVisible = true">{{ t('building.zone.batchAdd') }}</el-button>
            <el-button :icon="CopyDocument" size="small" :disabled="selectedRows.length === 0" @click="batchCopy">
              {{ t('building.zone.batchCopy') }}
            </el-button>
            <el-button type="danger" :icon="Delete" size="small" plain
              :disabled="selectedRows.length === 0" @click="batchDelete">
              {{ t('building.zone.batchDelete') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="pagedZones" size="small" stripe highlight-current-row
        @selection-change="handleSelectionChange"
        @row-click="handleRowClick"
        :row-class-name="({row}: {row: BuildingZone, rowIndex: number}) => editZones.indexOf(row) === selectedZoneIdx ? 'current-zone-row' : ''">
        <el-table-column type="selection" width="40" />
        <el-table-column label="#" width="55">
          <template #default="{ $index }">{{ (currentPage - 1) * pageSize + $index + 1 }}</template>
        </el-table-column>
        <el-table-column :label="t('building.zone.name')" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" :placeholder="t('building.zone.pleaseInputName')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('building.zone.area')" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.area" :min="0.1" size="small" :controls="false" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column :label="t('building.zone.floorHeight')" width="90">
          <template #default="{ row }">
            <el-input-number v-model="row.floor_height" :min="1" :max="50" :precision="1" size="small" :controls="false" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column :label="t('building.envelope.zonePosition')" width="90">
          <template #default="{ row }">
            <el-select v-model="row.zone_position" size="small" style="width: 100%">
              <el-option value="single" :label="t('building.envelope.position.single')" />
              <el-option value="top" :label="t('building.envelope.position.top')" />
              <el-option value="middle" :label="t('building.envelope.position.middle')" />
              <el-option value="bottom" :label="t('building.envelope.position.bottom')" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column :label="t('building.envelope.wallU')" width="80">
          <template #default="{ row }">
            <el-input-number v-model="row.wall_u_value" :min="0.01" :max="20" :precision="2" size="small" :controls="false" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column :label="t('building.envelope.windowU')" width="80">
          <template #default="{ row }">
            <el-input-number v-model="row.window_u_value" :min="0.1" :max="20" :precision="2" size="small" :controls="false" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column :label="t('building.envelope.wwr')" width="70">
          <template #default="{ row }">
            <el-input-number v-model="row.window_wall_ratio" :min="0" :max="1" :precision="2" size="small" :controls="false" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column :label="t('building.envelope.roofU')" width="80">
          <template #default="{ row }">
            <el-input-number v-model="row.roof_u_value" :min="0.01" :max="20" :precision="2" size="small" :controls="false" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column :label="t('common.operation')" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="copyZone(row)">{{ t('building.zone.copy') }}</el-button>
            <el-button link type="danger" size="small" @click.stop="removeZone(row)" :disabled="editZones.length <= 1">{{ t('building.zone.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="totalZones > 30"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 30, 50, 100]"
        :total="totalZones"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 12px; justify-content: flex-end"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- Batch add dialog -->
    <el-dialog v-model="batchAddVisible" :title="t('building.zone.batchAdd')" width="400px">
      <el-form label-width="100px">
        <el-form-item :label="t('building.zone.batchAddCount')">
          <el-input-number v-model="batchAddCount" :min="1" :max="50" />
        </el-form-item>
        <el-form-item :label="t('building.zone.batchAddPrefix')">
          <el-input v-model="batchAddName" :placeholder="t('building.zone.batchAddPrefixHint')" />
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
          <span>{{ activeZone.name || t('building.zone.title') + ' ' + (selectedZoneIdx + 1) }} — {{ t('building.zone.detailEdit') }}</span>
          <el-dropdown trigger="click" @command="applyPreset">
            <el-button size="small">
              {{ activePresetKey ? t(`building.zone.presets.${activePresetKey}`) : t('building.applyTemplate') }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
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
                <el-checkbox v-model="activeZone.wall_config.south_exterior">{{ t('building.envelope.wallDir.south') }}</el-checkbox>
                <el-checkbox v-model="activeZone.wall_config.north_exterior">{{ t('building.envelope.wallDir.north') }}</el-checkbox>
                <el-checkbox v-model="activeZone.wall_config.east_exterior">{{ t('building.envelope.wallDir.east') }}</el-checkbox>
                <el-checkbox v-model="activeZone.wall_config.west_exterior">{{ t('building.envelope.wallDir.west') }}</el-checkbox>
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Internal Gains -->
        <el-divider content-position="left">{{ t('building.internalGains.title') }}</el-divider>

        <div v-for="pm in PARAM_METAS" :key="pm.key" class="param-row">
          <div class="param-header">
            <span class="param-label">{{ t(pm.label) }}</span>
            <el-radio-group :model-value="getParam(activeZone, pm.key).mode"
              @update:model-value="v => switchMode(getParam(activeZone, pm.key), v)" size="small">
              <el-radio-button label="fixed">{{ t('building.schedule.fixed') }}</el-radio-button>
              <el-radio-button label="scheduled">{{ t('building.schedule.scheduled') }}</el-radio-button>
            </el-radio-group>
          </div>

          <!-- Fixed mode -->
          <div v-if="getParam(activeZone, pm.key).mode === 'fixed'" class="param-fixed">
            <el-input-number v-model="getParam(activeZone, pm.key).fixed_value"
              :min="pm.min" :max="pm.max" :precision="pm.precision" :step="pm.step" />
          </div>

          <!-- Scheduled mode -->
          <div v-else class="param-schedules">
            <div v-for="(sch, sIdx) in getParam(activeZone, pm.key).schedules" :key="sIdx"
              class="schedule-group" :class="{ 'schedule-conflict': isScheduleInConflict(getParam(activeZone, pm.key).schedules, sIdx) }">
              <!-- Conflict badge on conflicting group -->
              <el-tag v-if="isScheduleInConflict(getParam(activeZone, pm.key).schedules, sIdx)"
                type="danger" size="small" effect="dark" class="conflict-badge">
                {{ t('building.schedule.conflictWarning') }}
              </el-tag>
              <!-- Group header -->
              <div class="schedule-group-top">
                <el-input v-model="sch.name" size="small" :placeholder="t('building.schedule.dayGroupName')" style="width: 140px" />
                <div class="schedule-value-row">
                  <span class="schedule-sub-label">{{ t('building.schedule.value') }}:</span>
                  <el-input-number v-model="sch.value" :min="pm.min" :max="pm.max"
                    :precision="pm.precision" :step="pm.step" size="small" style="width: 140px" />
                </div>
                <el-button type="danger" link size="small" @click="removeDayGroup(getParam(activeZone, pm.key), sIdx)">
                  {{ t('building.schedule.removeSlot') }}
                </el-button>
              </div>

              <!-- Date range -->
              <div class="schedule-line">
                <span class="schedule-sub-label">{{ t('building.schedule.dateRange') }}:</span>
                <el-select v-model="sch.start_month" size="small" style="width: 80px">
                  <el-option v-for="m in 12" :key="m" :label="t(`building.schedule.monthNames.${m}`)" :value="m" />
                </el-select>
                <el-select v-model="sch.start_day" size="small" style="width: 70px">
                  <el-option v-for="d in (MONTH_DAYS[sch.start_month] || 31)" :key="d" :label="`${d}${t('building.schedule.dayUnit')}`" :value="d" />
                </el-select>
                <span class="schedule-sep">~</span>
                <el-select v-model="sch.end_month" size="small" style="width: 80px">
                  <el-option v-for="m in 12" :key="m" :label="t(`building.schedule.monthNames.${m}`)" :value="m" />
                </el-select>
                <el-select v-model="sch.end_day" size="small" style="width: 70px">
                  <el-option v-for="d in (MONTH_DAYS[sch.end_month] || 31)" :key="d" :label="`${d}${t('building.schedule.dayUnit')}`" :value="d" />
                </el-select>
              </div>

              <!-- Day checkboxes -->
              <div class="schedule-line">
                <span class="schedule-sub-label">{{ t('building.schedule.weekdays') }}:</span>
                <el-checkbox-group v-model="sch.days" size="small" class="day-checkboxes">
                  <el-checkbox-button v-for="d in [1,2,3,4,5,6,7]" :key="d" :label="d">
                    {{ t(`building.schedule.dayNames.${d}`) }}
                  </el-checkbox-button>
                </el-checkbox-group>
              </div>

              <!-- Hour checkboxes -->
              <div class="schedule-line schedule-hours-line">
                <div class="hours-header">
                  <span class="schedule-sub-label">{{ t('building.schedule.hours') }}:</span>
                  <div class="hours-quick">
                    <el-button link type="primary" size="small" @click="selectAllHours(sch)">{{ t('building.schedule.selectAll') }}</el-button>
                    <el-button link type="primary" size="small" @click="clearAllHours(sch)">{{ t('building.schedule.clearAll') }}</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 8, 18)">8~18</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 0, 8)">0~8</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 18, 24)">18~24</el-button>
                  </div>
                </div>
                <div class="hour-grid">
                  <label v-for="h in ALL_HOURS" :key="h" class="hour-cell"
                    :class="{ active: sch.hours.includes(h) }"
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

        <!-- Setpoints -->
        <el-divider content-position="left">{{ t('building.setpoint.title') }}</el-divider>

        <div v-for="pm in SETPOINT_METAS" :key="pm.key" class="param-row">
          <div class="param-header">
            <span class="param-label">{{ t(pm.label) }}</span>
            <el-radio-group :model-value="getParam(activeZone, pm.key).mode"
              @update:model-value="v => switchMode(getParam(activeZone, pm.key), v)" size="small">
              <el-radio-button label="fixed">{{ t('building.schedule.fixed') }}</el-radio-button>
              <el-radio-button label="scheduled">{{ t('building.schedule.scheduled') }}</el-radio-button>
            </el-radio-group>
          </div>

          <!-- Fixed mode -->
          <div v-if="getParam(activeZone, pm.key).mode === 'fixed'" class="param-fixed">
            <el-input-number v-model="getParam(activeZone, pm.key).fixed_value"
              :min="pm.min" :max="pm.max" :precision="pm.precision" :step="pm.step" />
          </div>

          <!-- Scheduled mode -->
          <div v-else class="param-schedules">
            <div v-for="(sch, sIdx) in getParam(activeZone, pm.key).schedules" :key="sIdx"
              class="schedule-group" :class="{ 'schedule-conflict': isScheduleInConflict(getParam(activeZone, pm.key).schedules, sIdx) }">
              <el-tag v-if="isScheduleInConflict(getParam(activeZone, pm.key).schedules, sIdx)"
                type="danger" size="small" effect="dark" class="conflict-badge">
                {{ t('building.schedule.conflictWarning') }}
              </el-tag>
              <div class="schedule-group-top">
                <el-input v-model="sch.name" size="small" :placeholder="t('building.schedule.dayGroupName')" style="width: 140px" />
                <div class="schedule-value-row">
                  <span class="schedule-sub-label">{{ t('building.schedule.value') }}:</span>
                  <el-input-number v-model="sch.value" :min="pm.min" :max="pm.max"
                    :precision="pm.precision" :step="pm.step" size="small" style="width: 140px" />
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
                  <el-option v-for="d in (MONTH_DAYS[sch.start_month] || 31)" :key="d" :label="`${d}${t('building.schedule.dayUnit')}`" :value="d" />
                </el-select>
                <span class="schedule-sep">~</span>
                <el-select v-model="sch.end_month" size="small" style="width: 80px">
                  <el-option v-for="m in 12" :key="m" :label="t(`building.schedule.monthNames.${m}`)" :value="m" />
                </el-select>
                <el-select v-model="sch.end_day" size="small" style="width: 70px">
                  <el-option v-for="d in (MONTH_DAYS[sch.end_month] || 31)" :key="d" :label="`${d}${t('building.schedule.dayUnit')}`" :value="d" />
                </el-select>
              </div>
              <div class="schedule-line">
                <span class="schedule-sub-label">{{ t('building.schedule.weekdays') }}:</span>
                <el-checkbox-group v-model="sch.days" size="small" class="day-checkboxes">
                  <el-checkbox-button v-for="d in [1,2,3,4,5,6,7]" :key="d" :label="d">
                    {{ t(`building.schedule.dayNames.${d}`) }}
                  </el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div class="schedule-line schedule-hours-line">
                <div class="hours-header">
                  <span class="schedule-sub-label">{{ t('building.schedule.hours') }}:</span>
                  <div class="hours-quick">
                    <el-button link type="primary" size="small" @click="selectAllHours(sch)">{{ t('building.schedule.selectAll') }}</el-button>
                    <el-button link type="primary" size="small" @click="clearAllHours(sch)">{{ t('building.schedule.clearAll') }}</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 8, 18)">8~18</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 0, 8)">0~8</el-button>
                    <el-button link type="primary" size="small" @click="toggleHourRange(sch, 18, 24)">18~24</el-button>
                  </div>
                </div>
                <div class="hour-grid">
                  <label v-for="h in ALL_HOURS" :key="h" class="hour-cell"
                    :class="{ active: sch.hours.includes(h) }"
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
  max-width: 1000px;
  margin: 0 auto;
}

/* ---- Header ---- */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left { flex: 1; min-width: 0; }
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
  cursor: pointer;
  border-bottom: 1px dashed transparent;
  transition: border-color 0.2s;
}
.header-name-row h1:hover { border-bottom-color: var(--el-color-primary); }
.edit-icon {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: color 0.2s;
}
.edit-icon:hover { color: var(--el-color-primary); }
.area-tag { font-size: 14px; font-weight: 600; }
.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* ---- Zone table ---- */
.zone-table-card {
  margin-bottom: 16px;
  border-radius: 8px;
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
.zone-card { border-radius: 8px; }
.zone-form { padding: 4px 0; }

/* ---- Internal gains ---- */
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
.param-fixed { padding-left: 4px; }

/* ---- Schedule ---- */
.param-schedules { padding-left: 4px; }
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
.day-checkboxes { flex-wrap: wrap; }

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
  .building-view { padding: 0 8px; }
  .page-header { flex-direction: column; }
  .zone-bar { flex-direction: column; align-items: stretch; }
  .zone-selector { width: 100%; }
  .param-header { flex-direction: column; align-items: flex-start; }
  .schedule-group-top { flex-direction: column; align-items: flex-start; }
  .schedule-line { flex-direction: column; align-items: flex-start; }
}
</style>