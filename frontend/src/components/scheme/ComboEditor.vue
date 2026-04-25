<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Delete } from '@element-plus/icons-vue'
import EquipmentPicker from './EquipmentPicker.vue'
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
}>()
const emit = defineEmits<{ 'update:modelValue': [v: SchemeCombo[]] }>()

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
    id: crypto.randomUUID(),
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

function issuesFor(idx: number): ValidationIssue[] {
  const cid = combos.value[idx]?.id
  if (!cid) return []
  const list = props.issues?.filter((i) => i.combo_id === cid) || []
  return [...list].sort((a, b) => (a.severity === 'error' ? 0 : 1) - (b.severity === 'error' ? 0 : 1))
}

function cleanMsg(msg: string): string {
  return msg
    .replace(/^子系统\[[^\]]+\]\s*/, '')
    .replace(/^组合\d+\s*/, '')
    .trim()
}

const isAirCooled = computed(() => props.schemeType === 'air_cooled')
const isFourPipe = computed(() => props.pipeSystem === 'four_pipe')

// 渐进式渲染 combo 块：首帧仅贴到 INITIAL_VISIBLE 个，之后用 setTimeout
// 在每帧之间留出绘制时间，让浏览器在两批之间完成一次合成，避免一次性挂载
// 10 个 combo 造成主线程冻结。
const INITIAL_VISIBLE = 1
const STEP = 1
const STEP_DELAY_MS = 32
const visibleCount = ref(0)
function scheduleProgressiveRender() {
  const total = combos.value.length
  visibleCount.value = Math.min(INITIAL_VISIBLE, total)
  if (visibleCount.value >= total) return
  const tick = () => {
    if (visibleCount.value >= combos.value.length) return
    visibleCount.value = Math.min(visibleCount.value + STEP, combos.value.length)
    if (visibleCount.value < combos.value.length) {
      setTimeout(tick, STEP_DELAY_MS)
    }
  }
  setTimeout(tick, STEP_DELAY_MS)
}
onMounted(scheduleProgressiveRender)
// 当用户点击“新增组合”时，应立即让新组合可见。
watch(
  () => combos.value.length,
  (n, prev) => {
    if (n > prev && visibleCount.value >= prev) visibleCount.value = n
  },
)
</script>

<template>
  <el-card shadow="never" class="combo-card">
    <template #header>
      <div class="combo-head">
        <span>{{ isAirCooled ? t('scheme.combo.titleAirCooled') : t('scheme.combo.title') }}</span>
        <el-button type="primary" :icon="Plus" size="small" @click="addCombo" :disabled="combos.length >= 10">
          {{ t('scheme.combo.add') }}
        </el-button>
      </div>
    </template>

    <template v-for="(combo, idx) in combos" :key="idx">
      <div v-if="idx < visibleCount" class="combo-block" :class="{ 'has-error': issuesFor(idx).some((i) => i.severity === 'error') }">
      <div class="combo-block-head">
        <strong>{{ t('scheme.combo.index') }} #{{ combo.combo_index }}</strong>
        <div class="combo-head-actions">
          <el-button size="small" @click="openFactorDialog(idx)">
            {{ t('scheme.combo.factorDialogBtn') }}
          </el-button>
          <el-button type="danger" :icon="Delete" size="small" text @click="removeCombo(idx)" :disabled="combos.length <= 1" />
        </div>
      </div>

      <el-alert
        v-for="(iss, i) in issuesFor(idx)"
        :key="`iss-${idx}-${i}`"
        :type="iss.severity === 'error' ? 'error' : 'warning'"
        :title="cleanMsg(iss.message)"
        show-icon
        :closable="false"
        class="combo-issue"
      />

      <!-- 冷机 / 风冷模块 输入行 -->
      <el-row :gutter="12" class="combo-row">
        <el-col :span="8">
          <el-form-item :label="isAirCooled ? t('scheme.combo.moduleModel') : t('scheme.combo.chillerModel')">
            <EquipmentPicker
              :model-value="combo.primary_model_id ?? null"
              :equipment-type="primaryType()"
              @update:model-value="(v) => onIdChange(idx, 'primary', v)"
              @pick="(eq) => onPicked(idx, 'primary', eq)"
            />
          </el-form-item>
        </el-col>
        <el-col :span="4"><el-form-item :label="isAirCooled ? t('scheme.combo.moduleCountPerGroup') : t('scheme.combo.chillerCount')">
          <el-input-number value-on-clear="min" v-model="combo.primary_count" :min="1" :max="20" size="small" />
        </el-form-item></el-col>
        <el-col v-if="isAirCooled" :span="4"><el-form-item :label="t('scheme.combo.groupCount')">
          <el-input-number value-on-clear="min" v-model="combo.group_count" :min="1" :max="10" size="small" /></el-form-item></el-col>
      </el-row>

      <!-- 冷机参数表 -->
      <el-descriptions
        v-if="derivedFor(idx) && combo.primary_model_id"
        :column="2"
        size="small"
        border
        class="device-table"
      >
        <el-descriptions-item v-if="derivedFor(idx)?.primary?.series" :label="t('scheme.derived.series')">
          {{ derivedFor(idx)?.primary?.series }}
        </el-descriptions-item>
        <el-descriptions-item v-if="derivedFor(idx)?.cop" label="COP">
          {{ derivedFor(idx)?.cop }} kW/kW
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.capacityLabel')">
          {{ unitVal(derivedFor(idx)?.cooling_capacity, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.cooling_capacity }} kW
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.powerLabel')">
          {{ unitVal(derivedFor(idx)?.power, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.power }} kW
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.evapFlowLabel')">
          {{ unitVal(derivedFor(idx)?.chw_flow, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.chw_flow }} m³/h
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.condFlowLabel')">
          {{ unitVal(derivedFor(idx)?.cw_flow, derivedFor(idx)?.primary_count) }} × {{ derivedFor(idx)?.primary_count }} = {{ derivedFor(idx)?.cw_flow }} m³/h
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.evapDpLabel')">
          {{ derivedFor(idx)?.evap_dp }} mH₂O
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.condDpLabel')">
          {{ derivedFor(idx)?.cond_dp }} mH₂O
        </el-descriptions-item>
      </el-descriptions>

      <!-- 冷冻水泵 输入行 -->
      <el-row :gutter="12" class="combo-row">
        <el-col :span="8">
          <el-form-item :label="isAirCooled && !isFourPipe ? t('scheme.combo.pumpModel') : t('scheme.combo.chwPumpModel')">
            <EquipmentPicker
              :model-value="combo.chw_pump_model_id ?? null"
              equipment-type="pump"
              @update:model-value="(v) => onIdChange(idx, 'chw', v)"
              @pick="(eq) => onPicked(idx, 'chw', eq)"
            />
          </el-form-item>
        </el-col>
        <el-col :span="4"><el-form-item :label="isAirCooled && !isFourPipe ? t('scheme.combo.pumpCount') : t('scheme.combo.chwPumpCount')">
          <el-input-number value-on-clear="min" v-model="combo.chw_pump_count" :min="1" :max="20" size="small" />
        </el-form-item></el-col>
        <el-col :span="4"><el-form-item :label="isAirCooled && !isFourPipe ? t('scheme.combo.pumpBackup') : t('scheme.combo.chwBackup')">
          <el-input-number value-on-clear="min" v-model="combo.chw_pump_backup" :min="0" :max="1" size="small" /></el-form-item></el-col>
        <el-col :span="6"><el-form-item :label="t('scheme.combo.connection')">
          <el-radio-group v-model="combo.chw_connection" size="small">
            <el-radio-button value="direct">{{ t('scheme.combo.direct') }}</el-radio-button>
            <el-radio-button value="parallel">{{ t('scheme.combo.parallel') }}</el-radio-button>
          </el-radio-group>
        </el-form-item></el-col>
      </el-row>

      <!-- 冷冻水泵参数表 -->
      <el-descriptions
        v-if="derivedFor(idx)?.chw_pump && combo.chw_pump_model_id"
        :column="2"
        size="small"
        border
        class="device-table device-table--cool"
      >
        <el-descriptions-item :label="t('scheme.derived.flowLabel')">
          {{ unitVal(derivedFor(idx)?.chw_pump?.flow, derivedFor(idx)?.chw_pump?.active_count) }} × {{ derivedFor(idx)?.chw_pump?.active_count }} = {{ derivedFor(idx)?.chw_pump?.flow }} m³/h
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.headLabel')">
          {{ derivedFor(idx)?.chw_pump?.head }} mH₂O
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.powerLabel')">
          {{ unitVal(derivedFor(idx)?.chw_pump?.power, derivedFor(idx)?.chw_pump?.active_count) }} × {{ derivedFor(idx)?.chw_pump?.active_count }} = {{ derivedFor(idx)?.chw_pump?.power }} kW
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.efficiencyLabel')">
          {{ derivedFor(idx)?.chw_pump?.efficiency }} %
        </el-descriptions-item>
      </el-descriptions>

      <!-- Second pump row: 制冷机房 always shows; 风冷模块仅在四管制时显示 -->
      <template v-if="schemeType === 'chiller_plant' || isFourPipe">
        <el-row :gutter="12" class="combo-row">
          <el-col :span="8">
            <el-form-item :label="isAirCooled ? t('scheme.combo.hwPumpModel') : t('scheme.combo.cwPumpModel')">
              <EquipmentPicker
                :model-value="combo.cw_pump_model_id ?? null"
                equipment-type="pump"
                @update:model-value="(v) => onIdChange(idx, 'cw', v)"
                @pick="(eq) => onPicked(idx, 'cw', eq)"
              />
            </el-form-item>
          </el-col>
          <el-col :span="4"><el-form-item :label="t('scheme.combo.cwPumpCount')">
            <el-input-number value-on-clear="min" v-model="combo.cw_pump_count" :min="1" :max="20" size="small" />
          </el-form-item></el-col>
          <el-col :span="4"><el-form-item :label="t('scheme.combo.cwBackup')">
            <el-input-number value-on-clear="min" v-model="combo.cw_pump_backup" :min="0" :max="1" size="small" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item :label="t('scheme.combo.connection')">
            <el-radio-group v-model="combo.cw_connection" size="small">
              <el-radio-button value="direct">{{ t('scheme.combo.direct') }}</el-radio-button>
              <el-radio-button value="parallel">{{ t('scheme.combo.parallel') }}</el-radio-button>
            </el-radio-group>
          </el-form-item></el-col>
        </el-row>

        <!-- 冷却 / 热水泵参数表 -->
        <el-descriptions
          v-if="derivedFor(idx)?.cw_pump && combo.cw_pump_model_id"
          :column="2"
          size="small"
          border
          class="device-table device-table--warm"
        >
          <el-descriptions-item :label="t('scheme.derived.flowLabel')">
            {{ unitVal(derivedFor(idx)?.cw_pump?.flow, derivedFor(idx)?.cw_pump?.active_count) }} × {{ derivedFor(idx)?.cw_pump?.active_count }} = {{ derivedFor(idx)?.cw_pump?.flow }} m³/h
          </el-descriptions-item>
          <el-descriptions-item :label="t('scheme.derived.headLabel')">
            {{ derivedFor(idx)?.cw_pump?.head }} mH₂O
          </el-descriptions-item>
          <el-descriptions-item :label="t('scheme.derived.powerLabel')">
            {{ unitVal(derivedFor(idx)?.cw_pump?.power, derivedFor(idx)?.cw_pump?.active_count) }} × {{ derivedFor(idx)?.cw_pump?.active_count }} = {{ derivedFor(idx)?.cw_pump?.power }} kW
          </el-descriptions-item>
          <el-descriptions-item :label="t('scheme.derived.efficiencyLabel')">
            {{ derivedFor(idx)?.cw_pump?.efficiency }} %
          </el-descriptions-item>
        </el-descriptions>
      </template>

      <el-divider v-if="idx < combos.length - 1" />
    </div>
    </template>

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
            <el-input-number
              value-on-clear="min"
              v-model="combos[factorDialog.idx].primary_factor"
              :min="0.10" :max="1.00" :step="0.01" :precision="2"
            />
          </el-form-item>
          <el-form-item :label="t('scheme.combo.factorChwPump')">
            <el-input-number
              value-on-clear="min"
              v-model="combos[factorDialog.idx].chw_pump_factor"
              :min="0.10" :max="1.00" :step="0.01" :precision="2"
            />
          </el-form-item>
          <el-form-item :label="t('scheme.combo.factorCwPump')">
            <el-input-number
              value-on-clear="min"
              v-model="combos[factorDialog.idx].cw_pump_factor"
              :min="0.10" :max="1.00" :step="0.01" :precision="2"
            />
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
.combo-card { border-radius: 12px; }
.combo-head { display: flex; justify-content: space-between; align-items: center; }
.combo-block { padding: 10px 0; }
.combo-block-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.combo-head-actions { display: flex; align-items: center; gap: 6px; }
.factor-tip { color: #94a3b8; font-size: 12px; margin-top: -4px; }
.combo-row :deep(.el-form-item) { margin-bottom: 10px; }
.combo-row :deep(.el-radio-group) { flex-wrap: nowrap; white-space: nowrap; }
.combo-row :deep(.el-input-number) { width: 100%; }
.combo-row :deep(.el-input) { width: 100%; }
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
.combo-issue { margin-bottom: 8px; }
.device-table { margin: 4px 0 12px 0; }
.device-table :deep(.el-descriptions__label) { width: 110px; color: #475569; background: #f8fafc; }
.device-table :deep(.el-descriptions__content) { color: #0f172a; }
.device-table--cool :deep(.el-descriptions__label) { background: #ecfeff; color: #0e7490; }
.device-table--cool :deep(.el-descriptions__content) { color: #0e7490; }
.device-table--warm :deep(.el-descriptions__label) { background: #fff7ed; color: #c2410c; }
.device-table--warm :deep(.el-descriptions__content) { color: #c2410c; }
</style>
