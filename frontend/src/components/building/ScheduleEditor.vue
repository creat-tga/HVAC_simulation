<script setup lang="ts">
import { computed, ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Delete, MagicStick } from '@element-plus/icons-vue'
import type { DaySchedule } from '@/types/building'

const props = defineProps<{
  modelValue: DaySchedule
  /** Peak / design value (the 100% reference) */
  peakValue: number
  /** Display unit (e.g. "人/m²", "W/m²", "m³/h·人") */
  unit?: string
  /** Whether this schedule is removable (false for the only one) */
  removable?: boolean
  /** Label for the parameter (e.g. "人员密度") */
  paramLabel?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [v: DaySchedule]
  'remove': []
}>()

const { t } = useI18n()

// Ensure hourly_ratios is a 24-length array
function normalizeRatios(s: DaySchedule): number[] {
  if (Array.isArray(s.hourly_ratios) && s.hourly_ratios.length === 24) {
    return s.hourly_ratios.map(v => Math.max(0, Math.min(100, Number(v) || 0)))
  }
  // Migrate legacy: hours[] + value (treat value as the absolute, derive ratio)
  const ratios = new Array(24).fill(0) as number[]
  if (Array.isArray(s.hours) && s.hours.length > 0 && props.peakValue > 0) {
    const ratio = Math.max(0, Math.min(100, (s.value / props.peakValue) * 100))
    for (const h of s.hours) {
      if (h >= 0 && h < 24) ratios[h] = ratio
    }
  }
  return ratios
}

const ratios = ref<number[]>(normalizeRatios(props.modelValue))

function commit() {
  const next: DaySchedule = {
    ...props.modelValue,
    hourly_ratios: [...ratios.value],
    // Keep legacy fields synced for backend backward compat
    hours: ratios.value
      .map((r, i) => (r > 0 ? i : -1))
      .filter(i => i >= 0),
    value: props.peakValue, // legacy field — backend will use hourly_ratios when present
  }
  emit('update:modelValue', next)
}

// ---- Bar interactions ----
const selectedHours = reactive<Set<number>>(new Set())
const editingHour = ref<number | null>(null)
const editingValue = ref<number>(0)

function toggleSelect(h: number, ev: MouseEvent) {
  if (ev.shiftKey) {
    if (selectedHours.has(h)) selectedHours.delete(h)
    else selectedHours.add(h)
  } else {
    selectedHours.clear()
    selectedHours.add(h)
    editingHour.value = h
    editingValue.value = ratios.value[h]
  }
}

function applyEdit() {
  if (editingHour.value === null) return
  const v = Math.max(0, Math.min(100, Math.round(editingValue.value)))
  ratios.value[editingHour.value] = v
  editingHour.value = null
  commit()
}

function cancelEdit() {
  editingHour.value = null
}

// ---- Drag-to-adjust ----
let dragHour = -1
let dragStartY = 0
let dragStartRatio = 0
const BAR_AREA_HEIGHT = 120

function onBarDragStart(h: number, ev: MouseEvent) {
  if (ev.shiftKey) return // selection mode
  dragHour = h
  dragStartY = ev.clientY
  dragStartRatio = ratios.value[h]
  window.addEventListener('mousemove', onBarDragMove)
  window.addEventListener('mouseup', onBarDragEnd)
  ev.preventDefault()
}

function onBarDragMove(ev: MouseEvent) {
  if (dragHour < 0) return
  const dy = dragStartY - ev.clientY
  const delta = (dy / BAR_AREA_HEIGHT) * 100
  const next = Math.max(0, Math.min(100, Math.round(dragStartRatio + delta)))
  ratios.value[dragHour] = next
}

function onBarDragEnd() {
  if (dragHour >= 0) {
    dragHour = -1
    commit()
  }
  window.removeEventListener('mousemove', onBarDragMove)
  window.removeEventListener('mouseup', onBarDragEnd)
}

// ---- Bulk fill ----
const bulkValue = ref<number>(100)
function applyBulk() {
  if (selectedHours.size === 0) {
    ElMessage.warning(t('building.schedule.editor.selectHoursFirst'))
    return
  }
  const v = Math.max(0, Math.min(100, Math.round(bulkValue.value)))
  for (const h of selectedHours) ratios.value[h] = v
  commit()
}

function selectAll() {
  selectedHours.clear()
  for (let i = 0; i < 24; i++) selectedHours.add(i)
}
function clearSelection() {
  selectedHours.clear()
}

// ---- Presets ----
function applyPreset(name: 'office' | 'allday' | 'night' | 'clear') {
  const arr = new Array(24).fill(0) as number[]
  if (name === 'office') {
    for (let h = 9; h <= 18; h++) arr[h] = 100
    arr[8] = 50
    arr[19] = 30
  } else if (name === 'allday') {
    for (let h = 0; h < 24; h++) arr[h] = 100
  } else if (name === 'night') {
    for (let h = 0; h < 6; h++) arr[h] = 100
    for (let h = 22; h < 24; h++) arr[h] = 100
  }
  ratios.value = arr
  commit()
}

// ---- Days-of-week ----
const DAYS = [
  { key: 1, label: '\u4e00' },
  { key: 2, label: '\u4e8c' },
  { key: 3, label: '\u4e09' },
  { key: 4, label: '\u56db' },
  { key: 5, label: '\u4e94' },
  { key: 6, label: '\u516d' },
  { key: 7, label: '\u65e5' },
]

function toggleDay(d: number) {
  const days = props.modelValue.days || []
  const idx = days.indexOf(d)
  let next: number[]
  if (idx >= 0) next = days.filter(x => x !== d)
  else next = [...days, d].sort()
  emit('update:modelValue', { ...props.modelValue, days: next })
}

function isDaySelected(d: number): boolean {
  return (props.modelValue.days || []).includes(d)
}

// ---- Date range ----
function updateField<K extends keyof DaySchedule>(key: K, val: DaySchedule[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}

// ---- Visualization ----
function ratioColor(r: number): string {
  if (r === 0) return '#e2e8f0'
  // gradient from light teal to deep teal
  const alpha = 0.25 + (r / 100) * 0.75
  return `rgba(8, 145, 178, ${alpha.toFixed(2)})`
}

function actualValue(r: number): string {
  return ((props.peakValue * r) / 100).toFixed(2)
}

const HOURS = computed(() => Array.from({ length: 24 }, (_, i) => i))
</script>

<template>
  <div class="sch-editor">
    <!-- Header: name + remove -->
    <div class="sch-header">
      <el-input
        :model-value="modelValue.name"
        size="small"
        :placeholder="t('building.schedule.editor.namePlaceholder')"
        class="sch-name"
        @update:model-value="(v: string) => updateField('name', v)"
      />
      <el-button
        v-if="removable"
        size="small"
        text
        type="danger"
        :icon="Delete"
        @click="emit('remove')"
      >
        {{ t('common.delete') }}
      </el-button>
    </div>

    <!-- Date range + days -->
    <div class="sch-range">
      <div class="range-group">
        <span class="range-label">{{ t('building.schedule.editor.dateRange') }}</span>
        <el-input-number
          :model-value="modelValue.start_month"
          :min="1" :max="12" size="small" :controls="false"
          style="width: 56px"
          @change="(v: any) => updateField('start_month', Number(v) || 1)"
        />
        <span class="dash">/</span>
        <el-input-number
          :model-value="modelValue.start_day"
          :min="1" :max="31" size="small" :controls="false"
          style="width: 56px"
          @change="(v: any) => updateField('start_day', Number(v) || 1)"
        />
        <span class="tilde">~</span>
        <el-input-number
          :model-value="modelValue.end_month"
          :min="1" :max="12" size="small" :controls="false"
          style="width: 56px"
          @change="(v: any) => updateField('end_month', Number(v) || 12)"
        />
        <span class="dash">/</span>
        <el-input-number
          :model-value="modelValue.end_day"
          :min="1" :max="31" size="small" :controls="false"
          style="width: 56px"
          @change="(v: any) => updateField('end_day', Number(v) || 31)"
        />
      </div>
      <div class="range-group">
        <span class="range-label">{{ t('building.schedule.editor.weekdays') }}</span>
        <div class="dow-list">
          <button
            v-for="d in DAYS"
            :key="d.key"
            type="button"
            class="dow-btn"
            :class="{ active: isDaySelected(d.key) }"
            @click="toggleDay(d.key)"
          >{{ d.label }}</button>
        </div>
      </div>
    </div>

    <!-- Bar chart -->
    <div class="sch-chart">
      <div class="chart-y-axis">
        <span>100%</span>
        <span>50%</span>
        <span>0%</span>
      </div>
      <div class="chart-bars">
        <div
          v-for="h in HOURS"
          :key="h"
          class="bar-col"
          :class="{ selected: selectedHours.has(h), editing: editingHour === h }"
          @click="(e) => toggleSelect(h, e)"
        >
          <div class="bar-track" :style="{ height: BAR_AREA_HEIGHT + 'px' }">
            <div
              class="bar-fill"
              :style="{
                height: (ratios[h] / 100 * BAR_AREA_HEIGHT) + 'px',
                background: ratioColor(ratios[h])
              }"
              :title="ratios[h] + '% \u2192 ' + actualValue(ratios[h]) + (unit ? ' ' + unit : '')"
              @mousedown="(e) => onBarDragStart(h, e)"
            >
              <span v-if="ratios[h] >= 18" class="bar-value">{{ ratios[h] }}</span>
            </div>
          </div>
          <div class="bar-hour">{{ h }}</div>
        </div>
      </div>
    </div>

    <!-- Inline value editor popup -->
    <div v-if="editingHour !== null" class="hour-edit-pop">
      <span class="hep-label">{{ editingHour }}:00</span>
      <el-input-number
        v-model="editingValue"
        :min="0" :max="100" :step="5" size="small" :precision="0"
        style="width: 110px"
      />
      <span class="hep-unit">%</span>
      <span class="hep-actual">→ {{ actualValue(editingValue) }} {{ unit }}</span>
      <el-button size="small" type="primary" @click="applyEdit">{{ t('common.confirm') }}</el-button>
      <el-button size="small" @click="cancelEdit">{{ t('common.cancel') }}</el-button>
    </div>

    <!-- Toolbar: presets + bulk -->
    <div class="sch-toolbar">
      <div class="toolbar-group">
        <span class="toolbar-label">{{ t('building.schedule.editor.preset') }}:</span>
        <el-button size="small" :icon="MagicStick" @click="applyPreset('office')">
          {{ t('building.schedule.editor.presetOffice') }}
        </el-button>
        <el-button size="small" @click="applyPreset('allday')">
          {{ t('building.schedule.editor.presetAllDay') }}
        </el-button>
        <el-button size="small" @click="applyPreset('night')">
          {{ t('building.schedule.editor.presetNight') }}
        </el-button>
        <el-button size="small" @click="applyPreset('clear')">
          {{ t('building.schedule.editor.presetClear') }}
        </el-button>
      </div>
      <div class="toolbar-group">
        <span class="toolbar-label">{{ t('building.schedule.editor.bulkFill') }}:</span>
        <el-input-number
          v-model="bulkValue"
          :min="0" :max="100" :step="10" size="small" :precision="0" :controls="false"
          style="width: 70px"
        />
        <span class="hep-unit">%</span>
        <el-button size="small" type="primary" plain @click="applyBulk">
          {{ t('building.schedule.editor.applyToSelected') }}
          <span v-if="selectedHours.size > 0" class="sel-badge">({{ selectedHours.size }})</span>
        </el-button>
        <el-button size="small" link @click="selectAll">{{ t('building.schedule.editor.selectAllHours') }}</el-button>
        <el-button v-if="selectedHours.size > 0" size="small" link @click="clearSelection">
          {{ t('building.schedule.editor.clearSelection') }}
        </el-button>
      </div>
    </div>

    <div class="sch-hint">
      <span>{{ t('building.schedule.editor.hint') }}</span>
    </div>
  </div>
</template>

<style scoped>
.sch-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.sch-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sch-name {
  flex: 1;
  max-width: 280px;
}
.sch-range {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.range-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.range-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}
.dash, .tilde {
  color: #94a3b8;
  font-weight: 600;
}
.dow-list {
  display: flex;
  gap: 4px;
}
.dow-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s ease;
}
.dow-btn:hover {
  border-color: #0891b2;
  color: #0891b2;
}
.dow-btn.active {
  background: #0891b2;
  color: #fff;
  border-color: #0891b2;
}

/* Chart */
.sch-chart {
  display: flex;
  gap: 8px;
  padding: 12px 8px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow-x: auto;
}
.chart-y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
  padding: 4px 0 22px 0;
  height: 120px;
  flex-shrink: 0;
}
.chart-bars {
  display: flex;
  flex: 1;
  min-width: 480px;
  gap: 2px;
}
.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  user-select: none;
}
.bar-track {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: linear-gradient(180deg, transparent 0%, transparent 49.5%, #f1f5f9 49.5%, #f1f5f9 50.5%, transparent 50.5%);
  border-radius: 3px;
  position: relative;
  transition: background 0.15s ease;
}
.bar-col:hover .bar-track {
  background: rgba(8, 145, 178, 0.06);
}
.bar-fill {
  width: 100%;
  border-radius: 3px 3px 0 0;
  cursor: ns-resize;
  transition: background 0.12s ease;
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
  box-sizing: border-box;
  min-height: 2px;
}
.bar-value {
  font-size: 9px;
  color: #fff;
  font-weight: 700;
  text-shadow: 0 0 2px rgba(0,0,0,0.3);
}
.bar-hour {
  font-size: 10px;
  color: #64748b;
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}
.bar-col.selected .bar-track {
  background: rgba(8, 145, 178, 0.16);
  outline: 1.5px solid #0891b2;
  border-radius: 3px;
}
.bar-col.editing .bar-track {
  background: rgba(245, 158, 11, 0.18);
  outline: 1.5px solid #f59e0b;
  border-radius: 3px;
}

/* Inline edit popup */
.hour-edit-pop {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #fef3c7, #fef9e7);
  border: 1px solid #f59e0b;
  border-radius: 8px;
  font-size: 13px;
}
.hep-label {
  font-weight: 700;
  color: #b45309;
  font-variant-numeric: tabular-nums;
}
.hep-unit {
  font-size: 12px;
  color: #64748b;
}
.hep-actual {
  font-size: 12px;
  color: #475569;
  flex: 1;
}

/* Toolbar */
.sch-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 0 0 0;
  border-top: 1px dashed #e2e8f0;
}
.toolbar-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.toolbar-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}
.sel-badge {
  margin-left: 4px;
  font-size: 11px;
  color: #0891b2;
}

.sch-hint {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
}

/* Mobile */
@media (max-width: 640px) {
  .sch-editor {
    padding: 10px;
  }
  .sch-range {
    flex-direction: column;
    gap: 10px;
  }
  .chart-bars {
    min-width: 360px;
  }
  .bar-hour {
    font-size: 9px;
  }
  .sch-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-group {
    flex-wrap: wrap;
  }
}
</style>
