<script setup lang="ts">
/**
 * ScheduleEditor — adopts hvac-simpro dark heatmap style
 *
 * Visual language: bg-zinc-900/50 card with bg-zinc-800 border, type-tinted
 * icon badge, heatmap row (alpha=value), JetBrains Mono numerics, sparse
 * 0h/12h/24h tick labels.
 *
 * Functionality preserved: cascading month/day selectors, weekday picker,
 * click-to-edit inline input, vertical drag, double-click reset, presets,
 * bulk fill, multi-select, conflict banner.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElIcon, ElCascader, ElAlert } from 'element-plus'
import { Delete, MagicStick, User, Sunny, Lightning, Position } from '@element-plus/icons-vue'
import type { DaySchedule } from '@/types/building'

type SchType = 'people' | 'lighting' | 'equipment' | 'fresh' | 'setpoint' | undefined

const props = defineProps<{
  modelValue: DaySchedule
  index?: number
  removable?: boolean
  conflictMessage?: string
  type?: SchType
  peakValue?: number
  unit?: string
  paramLabel?: string
  mode?: 'percent' | 'binary'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: DaySchedule): void
  (e: 'remove'): void
}>()

function ensureRatios(v: DaySchedule): number[] {
  if (Array.isArray(v.hourly_ratios) && v.hourly_ratios.length === 24) return [...v.hourly_ratios]
  // derive from legacy hours+value when needed
  const arr = Array(24).fill(0)
  if (Array.isArray(v.hours) && v.value) {
    v.hours.forEach(h => { if (h >= 0 && h < 24) arr[h] = 100 })
  }
  return arr
}

// helper to emit a partial patch (every field change must go through this)
function patch(p: Partial<DaySchedule>) {
  emit('update:modelValue', { ...props.modelValue, hourly_ratios: ensureRatios(props.modelValue), ...p })
}

// reactive view of underlying value (read-only proxy)
const ratios = computed(() => ensureRatios(props.modelValue))

// time axis tick hours (every 2 hours: 0,2,4,...,22)
const tickHours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]

const nameField = computed({
  get: () => props.modelValue.name,
  set: v => patch({ name: v })
})

// ===== type palette (hvac-simpro semantic colors) =====
const TYPE_PALETTE: Record<string, { rgb: string; tagZh: string; iconBg: string; iconColor: string; ringColor: string }> = {
  people: {
    rgb: '249, 115, 22',
    tagZh: '人员',
    iconBg: 'rgba(249, 115, 22, 0.1)',
    iconColor: '#f97316',
    ringColor: 'rgba(249, 115, 22, 0.55)'
  },
  lighting: {
    rgb: '234, 179, 8',
    tagZh: '照明',
    iconBg: 'rgba(234, 179, 8, 0.12)',
    iconColor: '#ca8a04',
    ringColor: 'rgba(234, 179, 8, 0.55)'
  },
  equipment: {
    rgb: '59, 130, 246',
    tagZh: '设备',
    iconBg: 'rgba(59, 130, 246, 0.1)',
    iconColor: '#3b82f6',
    ringColor: 'rgba(59, 130, 246, 0.55)'
  },
  fresh: {
    rgb: '20, 184, 166',
    tagZh: '新风',
    iconBg: 'rgba(20, 184, 166, 0.1)',
    iconColor: '#14b8a6',
    ringColor: 'rgba(20, 184, 166, 0.55)'
  },
  setpoint: {
    rgb: '14, 165, 233',
    tagZh: '温湿度',
    iconBg: 'rgba(14, 165, 233, 0.12)',
    iconColor: '#0284c7',
    ringColor: 'rgba(14, 165, 233, 0.55)'
  },
  default: {
    rgb: '139, 92, 246',
    tagZh: '通用',
    iconBg: 'rgba(139, 92, 246, 0.1)',
    iconColor: '#8b5cf6',
    ringColor: 'rgba(139, 92, 246, 0.55)'
  }
}

const TYPE_ICONS = { people: User, lighting: Sunny, equipment: Lightning, fresh: Position, setpoint: Sunny } as const

const palette = computed(() => TYPE_PALETTE[props.type || 'default'] || TYPE_PALETTE.default)
const typeIcon = computed(() => TYPE_ICONS[props.type as keyof typeof TYPE_ICONS] || User)

// ===== month / day cascading =====
const months = Array.from({ length: 12 }, (_, i) => ({ v: i + 1, label: `${i + 1}月` }))
const daysInMonth = (m: number) => new Date(2024, m, 0).getDate()
const dateOptions = computed(() => months.map(m => ({
  value: m.v,
  label: m.label,
  children: Array.from({ length: daysInMonth(m.v) }, (_, i) => ({ value: i + 1, label: `${i + 1}日` }))
})))
const startDateValue = computed<[number, number]>({
  get: (): [number, number] => [props.modelValue.start_month, props.modelValue.start_day],
  set: ([month, day]: [number, number]) => patch({ start_month: month, start_day: day })
})
const endDateValue = computed<[number, number]>({
  get: (): [number, number] => [props.modelValue.end_month, props.modelValue.end_day],
  set: ([month, day]: [number, number]) => patch({ end_month: month, end_day: day })
})
watch(() => props.modelValue.start_month, m => {
  const max = daysInMonth(m)
  if (props.modelValue.start_day > max) patch({ start_day: max })
})
watch(() => props.modelValue.end_month, m => {
  const max = daysInMonth(m)
  if (props.modelValue.end_day > max) patch({ end_day: max })
})

// ===== weekdays =====
const weekdayLabels = ['一', '二', '三', '四', '五', '六', '日']
const weekdayPaintState = ref<{ target: boolean } | null>(null)

function setWeekdaySelected(d: number, selected: boolean) {
  const days = [...(props.modelValue.days || [])]
  const idx = days.indexOf(d)
  if (selected && idx < 0) days.push(d)
  if (!selected && idx >= 0) days.splice(idx, 1)
  days.sort((a, b) => a - b)
  patch({ days })
}
const isWeekdaySelected = (d: number) => (props.modelValue.days || []).includes(d)
function toggleWeekday(d: number) {
  setWeekdaySelected(d, !isWeekdaySelected(d))
}
function onWeekdayPointerDown(e: PointerEvent, d: number) {
  if (e.button !== 0) return
  e.preventDefault()
  const target = !isWeekdaySelected(d)
  setWeekdaySelected(d, target)
  weekdayPaintState.value = { target }
  window.addEventListener('pointermove', onWeekdayPointerMove)
  window.addEventListener('pointerup', onWeekdayPointerEnd)
}
function onWeekdayPointerMove(e: PointerEvent) {
  if (!weekdayPaintState.value) return
  const el = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null
  const pill = el?.closest('[data-weekday]') as HTMLElement | null
  if (!pill) return
  const d = Number(pill.dataset.weekday)
  if (!Number.isNaN(d)) setWeekdaySelected(d, weekdayPaintState.value.target)
}
function onWeekdayPointerEnd() {
  weekdayPaintState.value = null
  window.removeEventListener('pointermove', onWeekdayPointerMove)
  window.removeEventListener('pointerup', onWeekdayPointerEnd)
}

// ===== editing =====
const editingHour = ref<number | null>(null)
const editingValue = ref<number>(0)
const editingInputRef = ref<HTMLInputElement | null>(null)
const isCompactViewport = ref(false)

function updateCompactViewport() {
  isCompactViewport.value = window.matchMedia('(max-width: 768px)').matches
}

function startEdit(h: number) {
  editingHour.value = h
  editingValue.value = ratios.value[h] ?? 0
  nextTick(() => {
    const el = Array.isArray(editingInputRef.value) ? editingInputRef.value[0] : editingInputRef.value
    el?.focus()
    el?.select()
  })
}

function commitEdit() {
  if (editingHour.value === null) return
  const h = editingHour.value
  const v = Math.max(0, Math.min(100, Math.round(editingValue.value || 0)))
  const arr = [...ratios.value]
  arr[h] = v
  patch({ hourly_ratios: arr })
  editingHour.value = null
}

function cancelEdit() {
  editingHour.value = null
}

function onCellDblClick(h: number) {
  const arr = [...ratios.value]
  arr[h] = 0
  patch({ hourly_ratios: arr })
  if (editingHour.value === h) editingHour.value = null
}

let suppressValueClickUntil = 0
function onValueCellClick(h: number) {
  if (Date.now() < suppressValueClickUntil) return
  startEdit(h)
}

// ===== drag (vertical) =====
const dragState = ref<{ hour: number; startY: number; startVal: number; moved: boolean } | null>(null)

function onCellMouseDown(e: MouseEvent, h: number) {
  if (e.button !== 0) return
  e.preventDefault() // suppress text selection start
  dragState.value = {
    hour: h,
    startY: e.clientY,
    startVal: ratios.value[h] ?? 0,
    moved: false
  }
  document.body.classList.add('sched-dragging')
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e: MouseEvent) {
  if (!dragState.value) return
  const dy = dragState.value.startY - e.clientY
  if (Math.abs(dy) < 3) return
  dragState.value.moved = true
  const newVal = Math.max(0, Math.min(100, Math.round(dragState.value.startVal + dy * 0.7)))
  const arr = [...ratios.value]
  arr[dragState.value.hour] = newVal
  patch({ hourly_ratios: arr })
}

function onDragEnd() {
  dragState.value = null
  document.body.classList.remove('sched-dragging')
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
}

const LONG_PRESS_MS = 500
let touchAdjustTimer: ReturnType<typeof setTimeout> | null = null
const touchAdjustState = ref<{ hour: number; startY: number; startVal: number; active: boolean } | null>(null)
const isValueTouchAdjusting = computed(() => Boolean(touchAdjustState.value?.active))

function clearTouchAdjustTimer() {
  if (touchAdjustTimer) {
    clearTimeout(touchAdjustTimer)
    touchAdjustTimer = null
  }
}

function onValueTouchStart(e: TouchEvent, h: number) {
  if (isBinary.value) return
  const touch = e.touches[0]
  if (!touch) return
  clearTouchAdjustTimer()
  touchAdjustState.value = {
    hour: h,
    startY: touch.clientY,
    startVal: ratios.value[h] ?? 0,
    active: false,
  }
  touchAdjustTimer = setTimeout(() => {
    const state = touchAdjustState.value
    if (!state || state.hour !== h) return
    state.active = true
    cancelEdit()
    document.body.classList.add('sched-dragging')
  }, LONG_PRESS_MS)
  window.addEventListener('touchmove', onValueTouchMove, { passive: false })
  window.addEventListener('touchend', onValueTouchEnd)
  window.addEventListener('touchcancel', onValueTouchEnd)
}

function onValueTouchMove(e: TouchEvent) {
  const state = touchAdjustState.value
  if (!state) return
  const touch = e.touches[0]
  if (!touch) return
  const dy = state.startY - touch.clientY
  if (!state.active) {
    if (Math.abs(dy) > 8) onValueTouchEnd()
    return
  }
  e.preventDefault()
  const nextValue = Math.max(0, Math.min(100, Math.round(state.startVal + dy * 0.6)))
  const arr = [...ratios.value]
  arr[state.hour] = nextValue
  patch({ hourly_ratios: arr })
}

function onValueTouchEnd() {
  const wasActive = touchAdjustState.value?.active
  clearTouchAdjustTimer()
  touchAdjustState.value = null
  document.body.classList.remove('sched-dragging')
  window.removeEventListener('touchmove', onValueTouchMove)
  window.removeEventListener('touchend', onValueTouchEnd)
  window.removeEventListener('touchcancel', onValueTouchEnd)
  if (wasActive) suppressValueClickUntil = Date.now() + 350
}

// ===== presets =====
function presetOffice9to18() {
  const arr = Array(24).fill(0)
  for (let h = 9; h < 18; h++) arr[h] = 100
  arr[8] = 30; arr[18] = 30
  patch({ hourly_ratios: arr })
}
function presetAlwaysOn() {
  patch({ hourly_ratios: Array(24).fill(100) })
}
function presetNight() {
  const arr = Array(24).fill(0)
  for (let h = 19; h < 24; h++) arr[h] = 100
  for (let h = 0; h < 7; h++) arr[h] = 100
  patch({ hourly_ratios: arr })
}
function presetClear() {
  patch({ hourly_ratios: Array(24).fill(0) })
}

// ===== mode (percent for building load schedules, binary on/off for HVAC run schedule) =====
const isBinary = computed(() => props.mode === 'binary')

// ===== heatmap cell style =====
function cellStyle(_h: number, val: number) {
  if (isBinary.value) {
    const on = val >= 50
    return { backgroundColor: on ? `rgba(${palette.value.rgb}, 0.85)` : 'rgba(148, 163, 184, 0.12)' }
  }
  const ratio = Math.max(0, Math.min(100, val)) / 100
  const alpha = ratio === 0 ? 0.06 : 0.18 + ratio * 0.82
  return { backgroundColor: `rgba(${palette.value.rgb}, ${alpha})` }
}

// ===== binary paint drag =====
const paintState = ref<{ target: number; lastHour: number } | null>(null)
function paintBinaryHour(h: number, target: number) {
  const arr = [...ratios.value]
  arr[h] = target
  patch({ hourly_ratios: arr })
}
function onBinaryMouseDown(e: MouseEvent, h: number) {
  if (e.button !== 0) return
  e.preventDefault()
  const cur = ratios.value[h] ?? 0
  const target = cur >= 50 ? 0 : 100
  paintBinaryHour(h, target)
  paintState.value = { target, lastHour: h }
  window.addEventListener('mousemove', onBinaryPaintMove)
  window.addEventListener('mouseup', onBinaryPaintEnd)
}
function onBinaryPaintMove(e: MouseEvent) {
  if (!paintState.value) return
  const el = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null
  const cellEl = el?.closest('[data-hour]') as HTMLElement | null
  if (!cellEl) return
  const h = Number(cellEl.dataset.hour)
  if (Number.isNaN(h) || h === paintState.value.lastHour) return
  paintBinaryHour(h, paintState.value.target)
  paintState.value.lastHour = h
}
function onBinaryPaintEnd() {
  paintState.value = null
  window.removeEventListener('mousemove', onBinaryPaintMove)
  window.removeEventListener('mouseup', onBinaryPaintEnd)
}
function onBinaryTouchStart(e: TouchEvent, h: number) {
  e.preventDefault()
  const cur = ratios.value[h] ?? 0
  const target = cur >= 50 ? 0 : 100
  paintBinaryHour(h, target)
  paintState.value = { target, lastHour: h }
  window.addEventListener('touchmove', onBinaryTouchMove, { passive: false })
  window.addEventListener('touchend', onBinaryTouchEnd)
  window.addEventListener('touchcancel', onBinaryTouchEnd)
}
function onBinaryTouchMove(e: TouchEvent) {
  if (!paintState.value) return
  e.preventDefault()
  const touch = e.touches[0]
  if (!touch) return
  const el = document.elementFromPoint(touch.clientX, touch.clientY) as HTMLElement | null
  const cellEl = el?.closest('[data-hour]') as HTMLElement | null
  if (!cellEl) return
  const h = Number(cellEl.dataset.hour)
  if (Number.isNaN(h) || h === paintState.value.lastHour) return
  paintBinaryHour(h, paintState.value.target)
  paintState.value.lastHour = h
}
function onBinaryTouchEnd() {
  paintState.value = null
  window.removeEventListener('touchmove', onBinaryTouchMove)
  window.removeEventListener('touchend', onBinaryTouchEnd)
  window.removeEventListener('touchcancel', onBinaryTouchEnd)
}

// ===== click-outside to commit edit =====
const cardRef = ref<HTMLElement | null>(null)
function onDocClick(e: MouseEvent) {
  if (!cardRef.value) return
  if (cardRef.value.contains(e.target as Node)) return
  if (editingHour.value !== null) {
    commitEdit()
  }
}
onMounted(() => {
  updateCompactViewport()
  window.addEventListener('resize', updateCompactViewport)
  document.addEventListener('mousedown', onDocClick)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateCompactViewport)
  document.removeEventListener('mousedown', onDocClick)
  onWeekdayPointerEnd()
  onBinaryPaintEnd()
  onBinaryTouchEnd()
  onValueTouchEnd()
})
</script>

<template>
  <div
    ref="cardRef"
    class="sched-card"
    :style="{
      '--accent': `rgb(${palette.rgb})`,
      '--accent-soft': `rgba(${palette.rgb}, 0.1)`,
      '--accent-border': `rgba(${palette.rgb}, 0.25)`,
      '--accent-rgb': palette.rgb
    }"
  >
    <!-- header -->
    <div class="sched-header">
      <div class="sched-header-left">
        <div class="type-badge" :style="{ background: palette.iconBg, color: palette.iconColor }">
          <el-icon :size="18"><component :is="typeIcon" /></el-icon>
        </div>
        <div class="sched-title-block">
          <input v-model="nameField" class="sched-name-input" :placeholder="`时间表 ${(props.index ?? 0) + 1}`" />
          <div class="sched-type-tag">{{ props.paramLabel || palette.tagZh }}时间表</div>
        </div>
      </div>
      <div class="sched-header-actions">
        <div v-if="!isCompactViewport" class="toolbar toolbar--header">
          <div class="tb-preset-row tb-preset-row--primary">
            <span class="tb-label">快捷预设</span>
            <button type="button" class="tb-btn" @click="presetOffice9to18">
              <el-icon :size="12"><MagicStick /></el-icon>办公9-18时
            </button>
          </div>
          <div class="tb-preset-row tb-preset-row--secondary">
            <button type="button" class="tb-btn" @click="presetAlwaysOn">全天</button>
            <button type="button" class="tb-btn" @click="presetNight">夜间</button>
            <button type="button" class="tb-btn tb-btn-danger" @click="presetClear">清空</button>
          </div>
        </div>
        <button type="button" v-if="removable !== false" class="del-btn" @click="emit('remove')" title="删除时间表">
          <el-icon :size="14"><Delete /></el-icon>
        </button>
      </div>
    </div>

    <!-- conflict banner -->
    <el-alert
      v-if="conflictMessage"
      :title="conflictMessage"
      type="warning"
      :closable="false"
      show-icon
      class="conflict-alert"
    />

    <slot name="before-meta" />

    <!-- date / weekday -->
    <div class="meta-row-wrap">
      <div class="meta-row">
          <div class="meta-label">日期</div>
      <div class="meta-controls">
        <el-cascader
          v-model="startDateValue"
          :options="dateOptions"
          size="small"
          class="meta-cascader"
          :show-all-levels="true"
          :clearable="false"
        />
        <span class="meta-sep">至</span>
        <el-cascader
          v-model="endDateValue"
          :options="dateOptions"
          size="small"
          class="meta-cascader"
          :show-all-levels="true"
          :clearable="false"
        />
      </div>
    </div>

    <div class="meta-row">
        <div class="meta-label">星期</div>
      <div class="weekday-pills">
        <button type="button"
          v-for="(label, i) in weekdayLabels"
          :key="i"
          :data-weekday="i + 1"
          class="weekday-pill"
          :class="{ 'is-active': isWeekdaySelected(i + 1) }"
          @pointerdown="onWeekdayPointerDown($event, i + 1)"
          @keydown.enter.prevent="toggleWeekday(i + 1)"
          @keydown.space.prevent="toggleWeekday(i + 1)"
        >
          {{ label }}
        </button>
      </div>
    </div>
    </div>

    <div v-if="isCompactViewport" class="toolbar toolbar--mobile-presets">
      <div class="tb-preset-row tb-preset-row--primary">
        <span class="tb-label">快捷预设</span>
        <button type="button" class="tb-btn" @click="presetOffice9to18">
          <el-icon :size="12"><MagicStick /></el-icon>办公9-18时
        </button>
      </div>
      <div class="tb-preset-row tb-preset-row--secondary">
        <button type="button" class="tb-btn" @click="presetAlwaysOn">全天</button>
        <button type="button" class="tb-btn" @click="presetNight">夜间</button>
        <button type="button" class="tb-btn tb-btn-danger" @click="presetClear">清空</button>
      </div>
    </div>

    <!-- heatmap with always-on top values (numbers are click-to-edit) -->
    <div class="time-row">
      <div class="meta-label">时刻</div>
      <div class="heatmap-wrap" :class="{ 'is-binary': isBinary }">
      <div class="hm-values" v-if="!isBinary && !isCompactViewport">
        <template v-for="(val, h) in ratios" :key="`v-${h}`">
          <div
            v-if="editingHour === h"
            class="hm-value hm-value-edit"
          >
            <input
              ref="editingInputRef"
              type="number"
              min="0"
              max="100"
              v-model.number="editingValue"
              class="hm-edit-input-inline"
              @keydown.enter.prevent="commitEdit"
              @keydown.esc.prevent="cancelEdit"
              @blur="commitEdit"
              @click.stop
            />
          </div>
          <div
            v-else
            class="hm-value"
            :class="{ 'is-zero': val === 0 }"
            @click="startEdit(h)"
            title="点击编辑数值"
          >{{ val }}</div>
        </template>
      </div>
      <div class="heatmap-row">
        <div
          v-for="(val, h) in ratios"
          :key="h"
          class="hm-cell"
          :class="{ 'is-zero': val === 0, 'is-on': isBinary && val >= 50, 'is-editing': editingHour === h, 'is-touch-adjusting': touchAdjustState?.active && touchAdjustState.hour === h }"
          :style="cellStyle(h, val)"
          :data-hour="h"
          :data-value="Math.round(val)"
          @mousedown="isBinary ? onBinaryMouseDown($event, h) : onCellMouseDown($event, h)"
          @touchstart="isBinary ? onBinaryTouchStart($event, h) : onValueTouchStart($event, h)"
          @click.stop="!isBinary && onValueCellClick(h)"
          @dblclick="!isBinary && onCellDblClick(h)"
          :title="isBinary ? '点击切换开关，按住拖动批量设置' : '长按后上下滑动调整数值'"
        >
          <div v-if="!isBinary && isCompactViewport && editingHour === h" class="hm-edit-pop hm-edit-pop-cell" @click.stop @mousedown.stop @touchstart.stop>
            <input
              ref="editingInputRef"
              type="number"
              min="0"
              max="100"
              v-model.number="editingValue"
              class="hm-edit-input"
              @keydown.enter.prevent="commitEdit"
              @keydown.esc.prevent="cancelEdit"
              @blur="commitEdit"
              @click.stop
              @touchstart.stop
            />
            <span class="hm-edit-suffix">%</span>
          </div>
        </div>
      </div>
      <div class="hm-ticks">
        <span v-for="t in tickHours" :key="t" class="hm-tick" :style="{ gridColumn: `${t + 1} / span 1` }">{{ t }}时</span>
      </div>
      </div>
    </div>

    <div class="sched-foot" v-if="!isBinary">
      {{ isValueTouchAdjusting ? '上下滑动调整数值 · 松手确认' : '长按矩形调值 · 点击数字精确编辑 · 双击矩形归零' }}
    </div>
    <div class="sched-foot" v-else>
      点击切换开关 · 按住拖动批量设置
    </div>
  </div>
</template>

<style scoped>
/* ===== unified font for entire component ===== */
.sched-card,
.sched-card * {
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', Roboto, sans-serif;
}

/* ===== card (light theme) ===== */
.sched-card {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: #18181b;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.sched-card:hover {
  border-color: var(--accent-border);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

/* ===== header ===== */
.sched-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.sched-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}
.type-badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sched-title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.sched-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  min-width: 0;
}
.sched-name-input {
  background: transparent;
  border: none;
  outline: none;
  color: #18181b;
  font-size: 14px;
  font-weight: 700;
  padding: 2px 0;
  width: 100%;
}
.sched-name-input:focus {
  border-bottom: 1px solid var(--accent);
}
.sched-name-input::placeholder {
  color: #a1a1aa;
}
.sched-type-tag {
  font-size: 11px;
  color: #a1a1aa;
  font-weight: 500;
}
.del-btn {
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
.del-btn:hover {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.4);
  color: #ef4444;
}

/* ===== conflict alert ===== */
.conflict-alert {
  background: rgba(234, 179, 8, 0.08) !important;
  border: 1px solid rgba(234, 179, 8, 0.25) !important;
}
.conflict-alert :deep(.el-alert__title) {
  color: #a16207;
  font-size: 12px;
}

/* ===== meta rows (date / weekdays) ===== */
.meta-row-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 32px;
  align-items: center;
}
.meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 1 auto;
  min-width: 0;
}
.meta-label {
  font-size: 12px;
  color: #71717a;
  font-weight: 500;
  flex-shrink: 0;
}
.meta-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.meta-select {
  width: 80px;
}
.meta-cascader {
  width: 118px;
}
.meta-select :deep(.el-select__wrapper) {
  background: #fafafa !important;
  border: 1px solid #e4e4e7 !important;
  box-shadow: none !important;
  color: #3f3f46 !important;
  font-size: 13px;
  min-height: 30px;
}
.meta-select :deep(.el-select__wrapper:hover) {
  border-color: #d4d4d8 !important;
}
.meta-select :deep(.el-select__placeholder) {
  color: #3f3f46 !important;
}
.meta-cascader :deep(.el-input__wrapper) {
  background: #fafafa !important;
  border: 1px solid #e4e4e7 !important;
  box-shadow: none !important;
  min-height: 30px;
  font-size: 13px;
}
.meta-cascader :deep(.el-input),
.meta-cascader :deep(.el-input__inner) {
  color: #3f3f46 !important;
  font-size: 13px !important;
}
.meta-sep {
  color: #a1a1aa;
  font-size: 13px;
}

/* ===== weekday pills ===== */
.weekday-pills {
  display: flex;
  gap: 6px;
  touch-action: none;
}
.weekday-pill {
  width: 32px;
  height: 30px;
  background: #fafafa;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  color: #71717a;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.weekday-pill:hover {
  border-color: #d4d4d8;
  color: #18181b;
}
.weekday-pill.is-active {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  color: var(--accent);
  font-weight: 600;
}

/* ===== heatmap ===== */
.time-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.time-row > .meta-label {
  line-height: 24px;
}
.heatmap-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.hm-values {
  display: grid;
  grid-template-columns: repeat(24, 1fr);
  gap: 4px;
  height: 22px;
}
.hm-value {
  text-align: center;
  font-size: 11px;
  color: #71717a;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  line-height: 22px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.12s;
  min-width: 0;
}
.hm-value:hover {
  background: #f4f4f5;
  color: #18181b;
}
.hm-value.is-zero {
  color: #d4d4d8;
}
.hm-value-edit {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid #fbbf24;
  border-radius: 4px;
  padding: 0;
  min-width: 0;
}
.hm-edit-input-inline {
  width: 100%;
  background: transparent;
  border: none;
  outline: none;
  color: #18181b;
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-align: center;
  appearance: textfield;
  -moz-appearance: textfield;
}
.hm-edit-input-inline::-webkit-outer-spin-button,
.hm-edit-input-inline::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.heatmap-row {
  display: grid;
  grid-template-columns: repeat(24, 1fr);
  gap: 4px;
  height: 56px;
  user-select: none;
}
.heatmap-wrap.is-binary .heatmap-row {
  height: 24px;
  gap: 3px;
}
.heatmap-wrap.is-binary .hm-cell {
  cursor: pointer;
  border-radius: 3px;
}
.heatmap-wrap.is-binary .hm-cell.is-on:hover {
  filter: brightness(0.95);
}
.heatmap-wrap.is-binary .hm-cell:not(.is-on):hover {
  background: rgba(148, 163, 184, 0.25) !important;
}
.hm-cell {
  border-radius: 4px;
  position: relative;
  cursor: row-resize;
  transition: filter 0.12s;
  background: #f4f4f5;
  min-width: 0;
}
.hm-cell:hover {
  filter: brightness(1.05);
}
.hm-cell.is-touch-adjusting {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(var(--accent-rgb), 0.16), 0 8px 18px rgba(var(--accent-rgb), 0.18);
  z-index: 2;
}
.hm-cell.is-touch-adjusting::before {
  content: '上下滑动';
  position: absolute;
  left: 50%;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  background: var(--accent);
  color: #ffffff;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 6px 16px rgba(var(--accent-rgb), 0.24);
  pointer-events: none;
}
.hm-cell.is-touch-adjusting::after {
  color: #ffffff;
}
.hm-cell.is-editing::after {
  display: none;
}
.hm-cell.is-zero {
  background: transparent;
  border: 1px dashed #e4e4e7;
}
.hm-edit-pop {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: #fbbf24;
  border-radius: 6px;
  padding: 4px 6px;
  display: flex;
  align-items: center;
  gap: 2px;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
  z-index: 20;
}
.hm-edit-pop::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #fbbf24;
}
.hm-edit-input {
  width: 44px;
  background: transparent;
  border: none;
  outline: none;
  color: #18181b;
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-align: center;
  appearance: textfield;
  -moz-appearance: textfield;
}
.hm-edit-input::-webkit-outer-spin-button,
.hm-edit-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.hm-edit-suffix {
  font-size: 11px;
  font-weight: 700;
  color: #18181b;
}
.hm-edit-pop-cell {
  display: none;
}
.hm-ticks {
  display: grid;
  grid-template-columns: repeat(24, 1fr);
  gap: 4px;
  font-size: 11px;
  color: #a1a1aa;
}
.hm-tick {
  text-align: center;
  min-width: 0;
  white-space: nowrap;
}
/* dragging-state class added on body during drag to suppress text selection */
body.sched-dragging,
body.sched-dragging * {
  user-select: none !important;
  cursor: row-resize !important;
}

/* ===== toolbar ===== */
.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding-top: 16px;
  border-top: 1px solid #f4f4f5;
}
.toolbar--header {
  padding-top: 0;
  border-top: 0;
  gap: 6px;
  flex-wrap: nowrap;
}
.toolbar--mobile-presets {
  display: none;
}
.tb-preset-row {
  display: contents;
}
.toolbar--header .tb-btn {
  padding: 5px 8px;
  white-space: nowrap;
}
.tb-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.tb-divider {
  width: 1px;
  height: 20px;
  background: #e4e4e7;
}
.tb-label {
  font-size: 12px;
  color: #71717a;
  font-weight: 500;
}
.tb-btn {
  background: #fafafa;
  border: 1px solid #e4e4e7;
  color: #3f3f46;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}
.tb-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-soft);
}
.tb-btn-danger:hover {
  border-color: rgba(239, 68, 68, 0.4);
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}
.tb-btn-accent {
  background: var(--accent-soft) !important;
  border-color: var(--accent-border) !important;
  color: var(--accent) !important;
  font-weight: 600;
}
.tb-btn-accent:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.tb-btn-link {
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 6px;
}
.tb-btn-link:hover {
  color: #18181b;
}
.tb-input {
  width: 60px;
  background: #fafafa;
  border: 1px solid #e4e4e7;
  color: #18181b;
  font-variant-numeric: tabular-nums;
  font-size: 13px;
  text-align: center;
  padding: 5px 6px;
  border-radius: 6px;
  outline: none;
  appearance: textfield;
  -moz-appearance: textfield;
}
.tb-input::-webkit-outer-spin-button,
.tb-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.tb-input:focus {
  border-color: var(--accent);
}
.tb-percent {
  color: #a1a1aa;
  font-size: 12px;
}

/* ===== foot tip ===== */
.sched-foot {
  font-size: 11px;
  color: #a1a1aa;
  text-align: center;
  padding-top: 4px;
}

@media (max-width: 900px) {
  .sched-card {
    position: relative;
    padding: 12px;
    gap: 12px;
    border-radius: 12px;
  }
  .sched-header {
    align-items: flex-start;
    gap: 8px;
  }
  .sched-header-left {
    flex: 1 1 auto;
    gap: 8px;
    padding-right: 34px;
  }
  .type-badge {
    width: 32px;
    height: 32px;
    border-radius: 8px;
  }
  .sched-title-block {
    flex: 1 1 auto;
    width: auto;
  }
  .sched-name-input {
    width: 100%;
  }
  .sched-type-tag {
    display: none;
  }
  .sched-header-actions {
    flex: 1 1 100%;
    justify-content: flex-start;
    margin-left: 40px;
    max-width: 100%;
  }
  .sched-header-actions .del-btn {
    position: absolute;
    top: 12px;
    right: 12px;
  }
  .toolbar--header {
    gap: 4px;
    flex-direction: column;
    align-items: flex-start;
    flex-wrap: nowrap;
    justify-content: flex-start;
    overflow: visible;
    width: 100%;
    max-width: 100%;
  }
  .toolbar--header .tb-preset-row {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 4px;
    width: 100%;
    min-width: 0;
    flex-wrap: wrap;
  }
  .toolbar--header .tb-preset-row--secondary {
    align-self: flex-start;
  }
  .toolbar--header .tb-label {
    flex: 0 0 auto;
    display: inline-flex;
    white-space: nowrap;
  }
  .toolbar--header .tb-btn {
    padding: 5px 7px;
    line-height: 1.2;
  }
  .toolbar--mobile-presets {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding-top: 0;
    border-top: 0;
    margin-top: -2px;
  }
  .toolbar--mobile-presets .tb-preset-row {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }
  .toolbar--mobile-presets .tb-preset-row--secondary {
    margin-left: 0;
  }
  .toolbar--mobile-presets .tb-label {
    white-space: nowrap;
  }
  .toolbar--mobile-presets .tb-btn {
    padding: 5px 7px;
    line-height: 1.2;
  }
  .meta-row-wrap {
    gap: 10px;
  }
  .time-row {
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 8px;
  }
  .meta-row {
    width: 100%;
    align-items: center;
  }
  .meta-controls {
    flex: 1;
    flex-wrap: nowrap;
  }
  .meta-cascader {
    width: 108px;
    min-width: 0;
  }
  .heatmap-wrap {
    overflow-x: visible;
    padding-bottom: 0;
  }
  .heatmap-wrap.is-binary .heatmap-row {
    grid-template-columns: repeat(12, minmax(0, 1fr));
    height: auto;
    gap: 4px;
  }
  .heatmap-wrap.is-binary .hm-cell {
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .heatmap-wrap.is-binary .hm-cell::after {
    content: attr(data-hour);
    font-size: 11px;
    font-weight: 700;
    color: rgba(15, 23, 42, 0.72);
    font-variant-numeric: tabular-nums;
  }
  .heatmap-wrap.is-binary .hm-cell.is-on::after {
    color: #ffffff;
  }
  .heatmap-wrap:not(.is-binary) .hm-values {
    display: none;
  }
  .heatmap-wrap:not(.is-binary) .heatmap-row {
    grid-template-columns: repeat(12, minmax(0, 1fr));
    height: auto;
    gap: 4px;
  }
  .heatmap-wrap:not(.is-binary) .hm-cell {
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    border: 1px dashed #e4e4e7;
  }
  .heatmap-wrap:not(.is-binary) .hm-cell::after {
    content: attr(data-value);
    color: #71717a;
    font-size: 12px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .heatmap-wrap:not(.is-binary) .hm-cell:not(.is-zero)::after {
    color: #ffffff;
  }
  .heatmap-wrap:not(.is-binary) .hm-cell.is-editing::after {
    display: none;
  }
  .heatmap-wrap:not(.is-binary) .hm-edit-pop {
    bottom: 50%;
    transform: translate(-50%, 50%);
  }
  .heatmap-wrap:not(.is-binary) .hm-edit-pop-cell {
    display: flex;
  }
  .heatmap-wrap:not(.is-binary) .hm-edit-pop::after {
    display: none;
  }
  .hm-ticks {
    display: none;
  }
}

@media (max-width: 420px) {
  .heatmap-wrap.is-binary .heatmap-row,
  .heatmap-wrap:not(.is-binary) .heatmap-row {
    grid-template-columns: repeat(8, minmax(0, 1fr));
  }
  .heatmap-wrap:not(.is-binary) .hm-cell {
    height: 34px;
  }
}

@media (max-width: 360px) {
  .meta-controls {
    flex-wrap: wrap;
  }
  .meta-cascader {
    width: calc(50% - 14px);
  }
  .meta-sep {
    width: auto;
    text-align: center;
  }
}
</style>

<style>
.sched-card .meta-cascader .el-input,
.sched-card .meta-cascader .el-input__wrapper,
.sched-card .meta-cascader .el-input__inner {
  font-size: 13px !important;
}
</style>
