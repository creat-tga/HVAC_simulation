<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowDown, ArrowRight, Plus, Delete } from '@element-plus/icons-vue'
import EquipmentPicker from './EquipmentPicker.vue'
import NumberInput from './NumberInput.vue'
import { randomUUID } from '@/utils/uuid'
import type {
  EquipmentBrief,
  EquipmentSearchParams,
  SchemeCombo,
  SchemeDerivedCombo,
  SubsystemType,
  ValidationIssue,
} from '@/types/system-scheme'

const { t } = useI18n()

const props = defineProps<{
  modelValue: SchemeCombo[]
  schemeType: SubsystemType
  pipeSystem?: 'two_pipe' | 'four_pipe'
  derived?: SchemeDerivedCombo[]
  issues?: ValidationIssue[]
  focusComboId?: string | null
  focusToken?: number
}>()
const emit = defineEmits<{ 'update:modelValue': [v: SchemeCombo[]] }>()
const COMBO_RENDER_BATCH_MS = 32

const combos = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// equipment cache for derived block display
const eqCache = ref<Record<string, EquipmentBrief>>({})

function primaryType(): EquipmentSearchParams['equipment_type'] {
  return props.schemeType === 'chiller_plant' ? 'chiller' : 'air_cooled_module'
}
function onPicked(comboIdx: number, field: 'primary' | 'chw' | 'cw', eq: EquipmentBrief) {
  eqCache.value[eq.id] = eq
  // model id is updated via v-model on EquipmentPicker; nothing else required here
  void comboIdx; void field
}
function onIdChange(comboIdx: number, field: 'primary' | 'chw' | 'cw', id: string | null) {
  const next = [...combos.value]
  const c = { ...next[comboIdx] }
  if (field === 'primary') c.primary_model_id = id
  if (field === 'chw') c.chw_pump_model_id = id
  if (field === 'cw') c.cw_pump_model_id = id
  next[comboIdx] = c
  combos.value = next
}

function addCombo() {
  if (combos.value.length >= 10) return
  const next: SchemeCombo = {
    // Pre-assign a stable client-side id so validation issues coming back
    // from the dry-run /validate-payload endpoint can be mapped to this
    // exact row via combo_id. Backend strips this id on actual save and
    // re-generates a fresh one in the DB.
    id: randomUUID(),
    combo_index: combos.value.length + 1,
    primary_model_id: null,
    primary_count: 1,
    primary_factor: 0.92,
    group_count: 1,
    chw_pump_model_id: null,
    chw_pump_count: 1,
    chw_pump_backup: 0,
    chw_connection: 'direct',
    chw_pump_factor: 0.77,
    cw_pump_model_id: null,
    cw_pump_count: 1,
    cw_pump_backup: 0,
    cw_connection: 'direct',
    cw_pump_factor: 0.77,
  }
  combos.value = [...combos.value, next]
  expandedComboKeys.value = new Set([comboKey(next, combos.value.length - 1)])
  visibleCount.value = combos.value.length
}

function removeCombo(idx: number) {
  if (combos.value.length <= 1) return
  combos.value = combos.value.filter((_, i) => i !== idx).map((c, i) => ({ ...c, combo_index: i + 1 }))
}

function getEqLabel(id: string | null) {
  if (!id) return ''
  const c = eqCache.value[id]
  if (c) return `${c.brand ?? ''} ${c.model_no ?? c.name}`.trim()
  return id.slice(0, 8)
}
void getEqLabel

function derivedFor(idx: number): SchemeDerivedCombo | undefined {
  return props.derived?.[idx]
}

function unitVal(total: number | undefined | null, count: number | undefined | null): number {
  if (!total || !count || count <= 0) return 0
  return Math.round((total / count) * 10) / 10
}

// 厂家参数弹窗
const factorDialog = ref<{ visible: boolean; idx: number }>({ visible: false, idx: -1 })
function openFactorDialog(idx: number) {
  factorDialog.value = { visible: true, idx }
}
function closeFactorDialog() {
  factorDialog.value.visible = false
}

const issuesByComboId = computed(() => {
  const map = new Map<string, ValidationIssue[]>()
  for (const issue of props.issues || []) {
    if (!issue.combo_id) continue
    const list = map.get(issue.combo_id) || []
    list.push(issue)
    map.set(issue.combo_id, list)
  }
  for (const [key, list] of map) {
    map.set(key, [...list].sort((a, b) => (a.severity === 'error' ? 0 : 1) - (b.severity === 'error' ? 0 : 1)))
  }
  return map
})

function comboIssues(combo: SchemeCombo): ValidationIssue[] {
  return combo.id ? issuesByComboId.value.get(combo.id) || [] : []
}

function comboHasError(combo: SchemeCombo): boolean {
  return comboIssues(combo).some((i) => i.severity === 'error')
}

function cleanMsg(msg: string): string {
  return msg
    .replace(/^子系统\[[^\]]+\]\s*/, '')
    .replace(/^组合\d+\s*/, '')
    .trim()
}

const isAirCooled = computed(() => props.schemeType === 'air_cooled')
const isFourPipe = computed(() => props.pipeSystem === 'four_pipe')
const visibleCount = ref(0)
const expandedComboKeys = ref<Set<string>>(new Set())
let renderTimer: ReturnType<typeof setTimeout> | null = null

const renderedCombos = computed(() => combos.value.slice(0, visibleCount.value))

function comboKey(combo: SchemeCombo, idx: number): string {
  return combo.id || `idx-${idx}`
}

function isComboExpanded(combo: SchemeCombo, idx: number): boolean {
  return expandedComboKeys.value.has(comboKey(combo, idx))
}

function toggleCombo(combo: SchemeCombo, idx: number) {
  const key = comboKey(combo, idx)
  const next = new Set(expandedComboKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedComboKeys.value = next
}

function scheduleBatchRender() {
  if (renderTimer || visibleCount.value >= combos.value.length) return
  renderTimer = setTimeout(() => {
    renderTimer = null
    visibleCount.value = Math.min(combos.value.length, visibleCount.value + 1)
    scheduleBatchRender()
  }, COMBO_RENDER_BATCH_MS)
}

watch(
  () => combos.value.length,
  (len, prev) => {
    if (renderTimer) {
      clearTimeout(renderTimer)
      renderTimer = null
    }
    if (len === 0) {
      visibleCount.value = 0
      expandedComboKeys.value = new Set()
      return
    }
    if (prev === undefined) {
      visibleCount.value = 1
      expandedComboKeys.value = len === 1 ? new Set([comboKey(combos.value[0], 0)]) : new Set()
      scheduleBatchRender()
      return
    }
    visibleCount.value = Math.min(Math.max(visibleCount.value, 1), len)
    scheduleBatchRender()
  },
  { immediate: true },
)

watch(
  () => [props.focusComboId, props.focusToken, combos.value.length] as const,
  ([comboId]) => {
    if (!comboId) return
    const idx = combos.value.findIndex((c) => c.id === comboId)
    if (idx < 0) return
    visibleCount.value = Math.max(visibleCount.value, idx + 1)
    const next = new Set(expandedComboKeys.value)
    next.add(comboKey(combos.value[idx], idx))
    expandedComboKeys.value = next
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (renderTimer) clearTimeout(renderTimer)
})

</script>

<template>
  <el-card shadow="never" class="combo-card">
    <template #header>
      <div class="combo-head">
        <span class="combo-title">{{ isAirCooled ? t('scheme.combo.titleAirCooled') : t('scheme.combo.title') }}</span>
        <el-button type="primary" :icon="Plus" size="small" @click="addCombo" :disabled="combos.length >= 10">
          {{ t('scheme.combo.add') }}
        </el-button>
      </div>
    </template>

    <template v-for="(combo, idx) in renderedCombos" :key="comboKey(combo, idx)">
      <div
        class="combo-block"
        :class="{ 'has-error': comboHasError(combo) }"
        :data-combo-id="combo.id || undefined"
      >
      <div class="combo-block-head">
        <button type="button" class="combo-toggle" @click="toggleCombo(combo, idx)">
          <el-icon><component :is="isComboExpanded(combo, idx) ? ArrowDown : ArrowRight" /></el-icon>
          <strong>{{ t('scheme.combo.index') }} #{{ combo.combo_index }}</strong>
        </button>
        <div class="combo-head-actions">
          <el-button size="small" text @click="openFactorDialog(idx)">
            {{ t('scheme.combo.factorDialogBtn') }}
          </el-button>
          <el-button type="danger" :icon="Delete" size="small" text @click="removeCombo(idx)" :disabled="combos.length <= 1" />
        </div>
      </div>

      <el-alert
        v-for="(iss, i) in comboIssues(combo)"
        :key="`iss-${idx}-${i}`"
        :type="iss.severity === 'error' ? 'error' : 'warning'"
        :title="cleanMsg(iss.message)"
        show-icon
        :closable="false"
        class="combo-issue"
      />

      <div v-if="!isComboExpanded(combo, idx)" class="combo-summary" @click="toggleCombo(combo, idx)">
        <!-- 冷机 / 风冷模块行：型号×台数  制冷量  COP -->
        <div class="summary-line summary-line--primary">
          <span class="summary-chip">
            {{ derivedFor(idx)?.primary?.model_no || derivedFor(idx)?.primary?.name || getEqLabel(combo.primary_model_id) || t('scheme.combo.pleasePick') }}<template v-if="combo.primary_count">×{{ combo.primary_count }}</template>
          </span>
          <span v-if="derivedFor(idx)?.cooling_capacity">{{ derivedFor(idx)?.cooling_capacity }}kW</span>
          <span v-if="derivedFor(idx)?.heating_capacity && !derivedFor(idx)?.cooling_capacity">{{ derivedFor(idx)?.heating_capacity }}kW</span>
          <span v-if="derivedFor(idx)?.cop">COP {{ derivedFor(idx)?.cop }}</span>
        </div>
        <!-- 冷冻水泵行：型号×台数(N备用)  流量  功率 -->
        <div v-if="combo.chw_pump_model_id" class="summary-line">
          <span class="summary-chip summary-chip--cool">
            {{ derivedFor(idx)?.chw_pump?.name || getEqLabel(combo.chw_pump_model_id) }}×{{ combo.chw_pump_count }}<template v-if="combo.chw_pump_backup > 0">({{ combo.chw_pump_backup }}{{ t('scheme.combo.backup') }})</template>
          </span>
          <span v-if="derivedFor(idx)?.chw_pump?.flow">{{ derivedFor(idx)?.chw_pump?.flow }}m³/h</span>
          <span v-if="derivedFor(idx)?.chw_pump?.power">{{ derivedFor(idx)?.chw_pump?.power }}kW</span>
        </div>
        <!-- 冷却水泵 / 热水泵行 -->
        <div v-if="(schemeType === 'chiller_plant' || isFourPipe) && combo.cw_pump_model_id" class="summary-line">
          <span class="summary-chip summary-chip--warm">
            {{ derivedFor(idx)?.cw_pump?.name || getEqLabel(combo.cw_pump_model_id) }}×{{ combo.cw_pump_count }}<template v-if="combo.cw_pump_backup > 0">({{ combo.cw_pump_backup }}{{ t('scheme.combo.backup') }})</template>
          </span>
          <span v-if="derivedFor(idx)?.cw_pump?.flow">{{ derivedFor(idx)?.cw_pump?.flow }}m³/h</span>
          <span v-if="derivedFor(idx)?.cw_pump?.power">{{ derivedFor(idx)?.cw_pump?.power }}kW</span>
        </div>
      </div>

      <template v-else>
      <!-- 冷机 / 风冷模块 输入行 -->
      <el-row :gutter="8" class="combo-row scheme-field-grid">
        <el-col :span="10">
          <el-form-item class="combo-picker-item" :label="isAirCooled ? t('scheme.combo.moduleModel') : t('scheme.combo.chillerModel')">
            <EquipmentPicker
              :model-value="combo.primary_model_id ?? null"
              :equipment-type="primaryType()"
              @update:model-value="(v) => onIdChange(idx, 'primary', v)"
              @pick="(eq) => onPicked(idx, 'primary', eq)"
            />
          </el-form-item>
        </el-col>
        <el-col :span="4"><el-form-item :label="isAirCooled ? t('scheme.combo.moduleCountPerGroup') : t('scheme.combo.chillerCount')">
          <NumberInput v-model="combo.primary_count" :min="1" :max="20" />
        </el-form-item></el-col>
        <el-col v-if="isAirCooled" :span="4"><el-form-item :label="t('scheme.combo.groupCount')">
          <NumberInput v-model="combo.group_count" :min="1" :max="10" /></el-form-item></el-col>
      </el-row>

      <!-- 冷机参数表 -->
      <div
        v-if="derivedFor(idx) && combo.primary_model_id"
        class="device-table"
      >
        <div v-if="derivedFor(idx)?.primary?.series" class="device-cell"><span>{{ t('scheme.derived.series') }}</span><strong>{{ derivedFor(idx)?.primary?.series }}</strong></div>
        <div v-if="derivedFor(idx)?.cop" class="device-cell"><span>COP</span><strong>{{ derivedFor(idx)?.cop }} kW/kW</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.capacityLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.cooling_capacity, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.cooling_capacity }} kW</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.powerLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.power, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.power }} kW</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.evapFlowLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.chw_flow, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.chw_flow }} m³/h</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.condFlowLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.cw_flow, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.cw_flow }} m³/h</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.evapDpLabel') }}</span><strong>{{ derivedFor(idx)?.evap_dp }} mH₂O</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.condDpLabel') }}</span><strong>{{ derivedFor(idx)?.cond_dp }} mH₂O</strong></div>
      </div>

      <!-- 冷冻水泵 输入行 -->
      <el-row :gutter="8" class="combo-row scheme-field-grid">
        <el-col :span="10">
          <el-form-item class="combo-picker-item" :label="isAirCooled && !isFourPipe ? t('scheme.combo.pumpModel') : t('scheme.combo.chwPumpModel')">
            <EquipmentPicker
              :model-value="combo.chw_pump_model_id ?? null"
              equipment-type="pump"
              @update:model-value="(v) => onIdChange(idx, 'chw', v)"
              @pick="(eq) => onPicked(idx, 'chw', eq)"
            />
          </el-form-item>
        </el-col>
        <el-col :span="4"><el-form-item :label="isAirCooled && !isFourPipe ? t('scheme.combo.pumpCount') : t('scheme.combo.chwPumpCount')">
          <NumberInput v-model="combo.chw_pump_count" :min="1" :max="20" />
        </el-form-item></el-col>
        <el-col :span="4"><el-form-item :label="isAirCooled && !isFourPipe ? t('scheme.combo.pumpBackup') : t('scheme.combo.chwBackup')">
          <NumberInput v-model="combo.chw_pump_backup" :min="0" :max="1" /></el-form-item></el-col>
        <el-col :span="6"><el-form-item class="scheme-field-item--auto" :label="t('scheme.combo.connection')">
          <el-radio-group v-model="combo.chw_connection" size="small">
            <el-radio value="direct">{{ t('scheme.combo.direct') }}</el-radio>
            <el-radio value="parallel">{{ t('scheme.combo.parallel') }}</el-radio>
          </el-radio-group>
        </el-form-item></el-col>
      </el-row>

      <!-- 冷冻水泵参数表 -->
      <div
        v-if="derivedFor(idx)?.chw_pump && combo.chw_pump_model_id"
        class="device-table device-table--cool"
      >
        <div class="device-cell"><span>{{ t('scheme.derived.flowLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.chw_pump?.flow, derivedFor(idx)?.chw_pump?.active_count) }} × {{ derivedFor(idx)?.chw_pump?.active_count }} = {{ derivedFor(idx)?.chw_pump?.flow }} m³/h</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.headLabel') }}</span><strong>{{ derivedFor(idx)?.chw_pump?.head }} mH₂O</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.powerLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.chw_pump?.power, derivedFor(idx)?.chw_pump?.active_count) }} × {{ derivedFor(idx)?.chw_pump?.active_count }} = {{ derivedFor(idx)?.chw_pump?.power }} kW</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.efficiencyLabel') }}</span><strong>{{ derivedFor(idx)?.chw_pump?.efficiency }} %</strong></div>
      </div>

      <!-- Second pump row: 制冷机房 always shows; 风冷模块仅在四管制时显示 -->
      <template v-if="schemeType === 'chiller_plant' || isFourPipe">
        <el-row :gutter="8" class="combo-row scheme-field-grid">
          <el-col :span="10">
            <el-form-item class="combo-picker-item" :label="isAirCooled ? t('scheme.combo.hwPumpModel') : t('scheme.combo.cwPumpModel')">
              <EquipmentPicker
                :model-value="combo.cw_pump_model_id ?? null"
                equipment-type="pump"
                @update:model-value="(v) => onIdChange(idx, 'cw', v)"
                @pick="(eq) => onPicked(idx, 'cw', eq)"
              />
            </el-form-item>
          </el-col>
          <el-col :span="4"><el-form-item :label="t('scheme.combo.cwPumpCount')">
            <NumberInput v-model="combo.cw_pump_count" :min="1" :max="20" />
          </el-form-item></el-col>
          <el-col :span="4"><el-form-item :label="t('scheme.combo.cwBackup')">
            <NumberInput v-model="combo.cw_pump_backup" :min="0" :max="1" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item class="scheme-field-item--auto" :label="t('scheme.combo.connection')">
            <el-radio-group v-model="combo.cw_connection" size="small">
              <el-radio value="direct">{{ t('scheme.combo.direct') }}</el-radio>
              <el-radio value="parallel">{{ t('scheme.combo.parallel') }}</el-radio>
            </el-radio-group>
          </el-form-item></el-col>
        </el-row>

        <!-- 冷却 / 热水泵参数表 -->
        <div
          v-if="derivedFor(idx)?.cw_pump && combo.cw_pump_model_id"
          class="device-table device-table--warm"
        >
          <div class="device-cell"><span>{{ t('scheme.derived.flowLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.cw_pump?.flow, derivedFor(idx)?.cw_pump?.active_count) }} × {{ derivedFor(idx)?.cw_pump?.active_count }} = {{ derivedFor(idx)?.cw_pump?.flow }} m³/h</strong></div>
          <div class="device-cell"><span>{{ t('scheme.derived.headLabel') }}</span><strong>{{ derivedFor(idx)?.cw_pump?.head }} mH₂O</strong></div>
          <div class="device-cell"><span>{{ t('scheme.derived.powerLabel') }}</span><strong>{{ unitVal(derivedFor(idx)?.cw_pump?.power, derivedFor(idx)?.cw_pump?.active_count) }} × {{ derivedFor(idx)?.cw_pump?.active_count }} = {{ derivedFor(idx)?.cw_pump?.power }} kW</strong></div>
          <div class="device-cell"><span>{{ t('scheme.derived.efficiencyLabel') }}</span><strong>{{ derivedFor(idx)?.cw_pump?.efficiency }} %</strong></div>
        </div>
      </template>
      </template>

      <el-divider v-if="idx < renderedCombos.length - 1" />
    </div>
    </template>

    <div v-if="visibleCount < combos.length" class="combo-progress">
      <el-skeleton :rows="2" animated />
    </div>

    <!-- 厂家参数弹窗 -->
    <el-dialog
      v-model="factorDialog.visible"
      :title="t('scheme.combo.factorDialogTitle')"
      width="480px"
      append-to-body
    >
      <template v-if="factorDialog.idx >= 0 && combos[factorDialog.idx]">
        <el-form label-width="140px" size="small">
          <el-form-item :label="t('scheme.combo.factorChiller')">
            <NumberInput v-model="combos[factorDialog.idx].primary_factor" :min="0.10" :max="1.00" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item :label="t('scheme.combo.factorChwPump')">
            <NumberInput v-model="combos[factorDialog.idx].chw_pump_factor" :min="0.10" :max="1.00" :step="0.01" :precision="2" />
          </el-form-item>
          <el-form-item :label="t('scheme.combo.factorCwPump')">
            <NumberInput v-model="combos[factorDialog.idx].cw_pump_factor" :min="0.10" :max="1.00" :step="0.01" :precision="2" />
          </el-form-item>
        </el-form>
        <div class="factor-tip">{{ t('scheme.combo.factorTip') }}</div>
      </template>
      <template #footer>
        <el-button @click="closeFactorDialog">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>

  </el-card>
</template>

<style scoped>
.combo-card { border-radius: 8px; }
.combo-card :deep(.el-card__header) { padding: 8px 10px; }
.combo-card :deep(.el-card__body) { padding: 8px 10px 10px; }
.combo-head { display: flex; justify-content: space-between; align-items: center; }
.combo-title { font-weight: 600; font-size: 14px; color: var(--text-primary); }
.combo-block {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.combo-block:last-of-type { border-bottom: 0; }
.combo-block-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.combo-head-actions { display: flex; align-items: center; gap: 6px; }
.combo-toggle {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #0f172a;
  cursor: pointer;
}
.combo-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 7px 9px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
}
.summary-main,
.summary-sub,
.summary-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 12px;
  color: #475569;
}
.summary-main { color: #0f172a; font-weight: 500; }
.summary-line--primary { color: #0f172a; font-weight: 500; }
.summary-chip {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.summary-chip--cool { color: #0e7490; }
.summary-chip--warm { color: #c2410c; }
.combo-progress { padding: 10px 0; }
.factor-tip { color: #94a3b8; font-size: 12px; margin-top: -4px; }
.eq-detail {
  margin-top: 4px;
  padding: 2px 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  display: flex;
  flex-wrap: wrap;
  gap: 2px 8px;
}
.eq-detail span { white-space: nowrap; }
.eq-detail span:not(:last-child)::after {
  content: '·';
  color: #cbd5e1;
  margin-left: 8px;
}
.eq-detail--cool span { color: #0e7490; }
.eq-detail--warm span { color: #c2410c; }
.combo-block.has-error { background: #fef2f2; border-radius: 8px; padding: 6px 8px; }
.combo-issue { margin-bottom: 6px; }
.device-table {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  margin: 2px 0 8px 0;
}
.device-cell {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  min-height: 28px;
  border-bottom: 1px solid #e2e8f0;
}
.device-cell:nth-last-child(-n + 2) { border-bottom: 0; }
.device-cell span {
  padding: 6px 8px;
  background: #f8fafc;
  color: #475569;
  font-weight: 500;
  font-size: 12px;
}
.device-cell strong {
  padding: 6px 8px;
  color: #0f172a;
  font-weight: 500;
  font-size: 12px;
  min-width: 0;
}
.device-table--cool .device-cell span { background: #ecfeff; color: #0e7490; }
.device-table--cool .device-cell strong { color: #0e7490; }
.device-table--warm .device-cell span { background: #fff7ed; color: #c2410c; }
.device-table--warm .device-cell strong { color: #c2410c; }

@media (max-width: 640px) {
  .combo-card :deep(.el-card__body) { padding: 8px; }
  /* 保持 展开按钮+组合名+厂家参数+删除 在同一行，只是压缩间距 */
  .combo-block-head {
    flex-wrap: nowrap;
    align-items: center;
    gap: 6px;
  }
  .combo-head-actions {
    flex: 0 0 auto;
    gap: 4px;
  }
  .summary-chip { max-width: 100%; }
  .device-table {
    grid-template-columns: minmax(0, 1fr);
  }
  .device-cell,
  .device-cell:nth-last-child(-n + 2) {
    grid-template-columns: 92px minmax(0, 1fr);
    border-bottom: 1px solid #e2e8f0;
  }
  .device-cell:last-child { border-bottom: 0; }
}

</style>
