<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getBuilding, updateBuilding } from '@/api/buildings'
import type { Building, BuildingUpdate, BuildingZone, ParamConfig, DaySchedule } from '@/types/building'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Plus, Delete, ArrowDown } from '@element-plus/icons-vue'
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

// ----- Global conflict check across all zones and params -----
const hasAnyConflict = computed(() => {
  for (const zone of editZones.value) {
    for (const pm of ALL_PARAM_METAS) {
      const param = getParam(zone, pm.key)
      if (param.mode === 'scheduled' && getConflicts(param.schedules).length > 0) return true
    }
  }
  return false
})

// ----- Unsaved changes detection -----
const savedSnapshot = ref('')

function getStateSnapshot(): string {
  return JSON.stringify({ name: editName.value, zones: editZones.value })
}

const isDirty = computed(() => {
  if (!savedSnapshot.value) return false
  return getStateSnapshot() !== savedSnapshot.value
})

// ----- Zone management -----
const activeZone = computed(() => editZones.value[selectedZoneIdx.value] ?? null)

const zoneOptions = computed(() =>
  editZones.value.map((z, idx) => ({
    value: idx,
    label: `${z.name || t('building.zone.title') + ' ' + (idx + 1)}  (${z.area || 0} m²)`,
  }))
)

function addZone() {
  editZones.value.push(createDefaultZone())
  nextTick(() => {
    selectedZoneIdx.value = editZones.value.length - 1
    activePresetKey.value = ''
  })
}

async function removeCurrentZone() {
  if (editZones.value.length <= 1) {
    ElMessage.warning(t('building.zone.lastZoneHint'))
    return
  }
  await ElMessageBox.confirm(t('building.zone.deleteConfirm'), t('common.warning'), { type: 'warning' })
  const idx = selectedZoneIdx.value
  editZones.value.splice(idx, 1)
  selectedZoneIdx.value = Math.min(idx, editZones.value.length - 1)
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
  return {
    name: raw.name || '',
    area: raw.area || 0,
    floor_height: raw.floor_height ?? 3.5,
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

// ----- Save -----
async function handleSave() {
  if (hasAnyConflict.value) {
    ElMessage.error(t('building.schedule.cannotSaveConflict'))
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

    <!-- Zone selector bar -->
    <div class="zone-bar">
      <el-select v-model="selectedZoneIdx" filterable :placeholder="t('building.zone.searchPlaceholder')"
        class="zone-selector">
        <el-option v-for="opt in zoneOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <span class="zone-count">{{ editZones.length }} {{ t('building.zone.title') }}</span>
      <el-button type="primary" :icon="Plus" size="small" @click="addZone">{{ t('building.zone.add') }}</el-button>
      <el-button type="danger" :icon="Delete" size="small" plain @click="removeCurrentZone"
        :disabled="editZones.length <= 1">{{ t('building.zone.delete') }}</el-button>
    </div>

    <!-- Active zone detail -->
    <el-card v-if="activeZone" class="zone-card" shadow="never">
      <el-form label-position="top" class="zone-form">
        <!-- Zone name + area + preset dropdown -->
        <el-row :gutter="16">
          <el-col :xs="24" :sm="6">
            <el-form-item :label="t('building.zone.name')">
              <el-input v-model="activeZone.name" :placeholder="t('building.zone.pleaseInputName')" :maxlength="20" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="4">
            <el-form-item :label="t('building.zone.area')">
              <el-input-number v-model="activeZone.area" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="4">
            <el-form-item :label="t('building.zone.floorHeight')">
              <el-input-number v-model="activeZone.floor_height" :min="2" :max="20" :precision="1" :step="0.5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="6">
            <el-form-item :label="t('building.applyTemplate')">
              <el-dropdown trigger="click" @command="applyPreset">
                <el-button size="default" style="width: 100%">
                  {{ activePresetKey ? t(`building.zone.presets.${activePresetKey}`) : t('building.zone.presets.custom') }}
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
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Envelope -->
        <el-divider content-position="left">{{ t('building.envelope.title') }}</el-divider>
        <el-row :gutter="16">
          <el-col :xs="12" :sm="6">
            <el-form-item :label="t('building.envelope.wallU')">
              <el-input-number v-model="activeZone.wall_u_value" :min="0.1" :max="5" :precision="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-form-item :label="t('building.envelope.windowU')">
              <el-input-number v-model="activeZone.window_u_value" :min="0.5" :max="6" :precision="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-form-item :label="t('building.envelope.wwr')">
              <el-input-number v-model="activeZone.window_wall_ratio" :min="0.05" :max="0.9" :precision="2" :step="0.05" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-form-item :label="t('building.envelope.roofU')">
              <el-input-number v-model="activeZone.roof_u_value" :min="0.1" :max="3" :precision="2" :step="0.1" style="width: 100%" />
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

/* ---- Zone bar ---- */
.zone-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}
.zone-selector { width: 320px; max-width: 100%; }
.zone-count {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
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