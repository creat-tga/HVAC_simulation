<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Delete } from '@element-plus/icons-vue'
import EquipmentPicker from './EquipmentPicker.vue'
import NumberInput from './NumberInput.vue'
import { randomUUID } from '@/utils/uuid'
import type { EquipmentBrief, SubsystemDerived, SchemeTowerGroup, ValidationIssue } from '@/types/system-scheme'

const { t } = useI18n()

const props = defineProps<{
  modelValue: SchemeTowerGroup[]
  derived?: SubsystemDerived | null
  issues?: ValidationIssue[]
}>()
const emit = defineEmits<{ 'update:modelValue': [v: SchemeTowerGroup[]] }>()

const groups = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const eqCache = ref<Record<string, EquipmentBrief>>({})

function onIdChange(i: number, id: string | null) {
  const next = [...groups.value]
  next[i] = { ...next[i], tower_model_id: id }
  groups.value = next
}
function onPicked(eq: EquipmentBrief) {
  eqCache.value[eq.id] = eq
}
function add() {
  if (groups.value.length >= 10) return
  groups.value = [
    ...groups.value,
    // Pre-assign a stable client-side id so validation issues from
    // /validate-payload can map back to this exact row.
    { id: randomUUID(), group_index: groups.value.length + 1, tower_model_id: null, count: 1, factor: 0.85 },
  ]
}
function remove(i: number) {
  if (groups.value.length <= 1) return
  groups.value = groups.value
    .filter((_, idx) => idx !== i)
    .map((g, idx) => ({ ...g, group_index: idx + 1 }))
}
function label(id: string | null) {
  if (!id) return ''
  const c = eqCache.value[id]
  if (c) return `${c.brand ?? ''} ${c.model_no ?? c.name}`.trim()
  return id.slice(0, 8)
}
void label

const requiredFlow = computed(() => {
  if (!props.derived) return 0
  return props.derived.combos.reduce((s, c) => s + c.cw_flow, 0)
})
const supplyFlow = computed(() => props.derived?.tower_flow_total ?? 0)

const factorDialogVisible = ref(false)
const factorDialogIndex = ref<number | null>(null)
const factorDraft = ref(0.85)

function openFactorDialog(idx: number) {
  factorDialogIndex.value = idx
  factorDraft.value = groups.value[idx]?.factor ?? 0.85
  factorDialogVisible.value = true
}

function applyFactor() {
  const idx = factorDialogIndex.value
  if (idx === null) return
  groups.value = groups.value.map((g, i) => (i === idx ? { ...g, factor: factorDraft.value } : g))
  factorDialogVisible.value = false
  factorDialogIndex.value = null
}

function towerIssues(idx: number): ValidationIssue[] {
  const tg = groups.value[idx]
  if (!tg) return []
  const list = (props.issues || []).filter((i) => {
    if (i.combo_id) return false
    // Prefer matching by stable tower-group id when present
    if (tg.id && i.field?.includes(`tower_groups[${idx}]`)) return true
    if (tg.id && i.field?.endsWith(`[${idx}].tower_model_id`)) return true
    // Fallback: match by index encoded in field (`tower_groups[<idx>]`)
    if (i.field?.includes(`tower_groups[${idx}]`)) return true
    // Generic tower-flow / tower-mismatch issues that aren't tied to a
    // specific group index should only show on the FIRST group, so we
    // don't duplicate them across every row.
    if (!i.field && idx === 0 && (i.code?.startsWith('CP_TOWER_') && i.code !== 'CP_TOWER_MISSING')) return true
    return false
  })
  return [...list].sort((a, b) => (a.severity === 'error' ? 0 : 1) - (b.severity === 'error' ? 0 : 1))
}

function cleanMsg(msg: string): string {
  return msg
    .replace(/^子系统\[[^\]]+\]\s*/, '')
    .replace(/^组合\d+\s*/, '')
    .trim()
}

function unitVal(total: number | undefined | null, count: number | undefined | null): number {
  if (!total || !count || count <= 0) return 0
  return Math.round((total / count) * 10) / 10
}
</script>

<template>
  <el-card shadow="never" class="tower-card">
    <template #header>
      <div class="tower-head">
        <span class="tower-title">{{ t('scheme.tower.title') }}</span>
        <div class="tower-head-actions">
          <el-button type="primary" :icon="Plus" size="small" @click="add" :disabled="groups.length >= 10">
            {{ t('scheme.tower.add') }}
          </el-button>
        </div>
      </div>
    </template>

    <div v-for="(g, idx) in groups" :key="idx" class="tower-row" :class="{ 'has-error': towerIssues(idx).some((i) => i.severity === 'error') }">
      <div class="tower-block-head">
        <strong>{{ t('scheme.tower.group') }} #{{ g.group_index }}</strong>
        <div class="tower-head-actions">
          <el-button size="small" text @click="openFactorDialog(idx)">
            {{ t('scheme.combo.factorDialogBtn') }}
          </el-button>
          <el-button type="danger" :icon="Delete" size="small" text @click="remove(idx)" :disabled="groups.length <= 1" />
        </div>
      </div>
      <el-alert
        v-for="(iss, i) in towerIssues(idx)"
        :key="`tiss-${idx}-${i}`"
        :type="iss.severity === 'error' ? 'error' : 'warning'"
        :title="cleanMsg(iss.message)"
        show-icon
        :closable="false"
        class="tower-issue"
      />
      <el-row :gutter="8" align="middle" class="tower-edit-row scheme-field-grid">
        <el-col :span="10" class="scheme-field-col--picker"><el-form-item :label="t('scheme.tower.model')">
          <EquipmentPicker
            :model-value="g.tower_model_id ?? null"
            equipment-type="cooling_tower"
            @update:model-value="(v) => onIdChange(idx, v)"
            @pick="onPicked"
          />
        </el-form-item></el-col>
        <el-col :span="4" class="scheme-field-col--number"><el-form-item :label="t('scheme.tower.count')">
          <NumberInput v-model="g.count" :min="1" :max="20" /></el-form-item></el-col>
      </el-row>

      <!-- 冷却塔参数表 -->
      <div
        v-if="derived?.tower_groups?.[idx] && g.tower_model_id"
        class="device-table device-table--warm"
      >
        <div class="device-cell"><span>{{ t('scheme.derived.flowLabel') }}</span><strong>{{ unitVal(derived.tower_groups[idx].flow, derived.tower_groups[idx].count) }} × {{ derived.tower_groups[idx].count }} = {{ derived.tower_groups[idx].flow }} m³/h</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.headLabel') }}</span><strong>{{ derived.tower_groups[idx].head }} mH₂O</strong></div>
        <div class="device-cell"><span>{{ t('scheme.derived.powerLabel') }}</span><strong>{{ unitVal(derived.tower_groups[idx].power, derived.tower_groups[idx].count) }} × {{ derived.tower_groups[idx].count }} = {{ derived.tower_groups[idx].power }} kW</strong></div>
        <div class="device-cell"><span>{{ t('scheme.tower.inletTemp') }}</span><strong>{{ derived.tower_groups[idx].inlet_temp }} ℃</strong></div>
        <div class="device-cell"><span>{{ t('scheme.tower.outletTemp') }}</span><strong>{{ derived.tower_groups[idx].outlet_temp }} ℃</strong></div>
        <div class="device-cell"><span>{{ t('scheme.tower.wetBulb') }}</span><strong>{{ derived.tower_groups[idx].wet_bulb }} ℃</strong></div>
      </div>
    </div>

    <div v-if="derived" class="tower-summary">
      <div class="tower-summary-item">
        <span>{{ t('scheme.tower.flowRequired') }}</span>
        <strong>{{ requiredFlow.toFixed(1) }} m³/h</strong>
      </div>
      <div class="tower-summary-item">
        <span>{{ t('scheme.tower.flowSupply') }}</span>
        <strong :style="{ color: Math.abs(supplyFlow - requiredFlow) / Math.max(requiredFlow, 1) > 0.1 ? 'var(--color-danger)' : 'var(--color-success)' }">
          {{ supplyFlow.toFixed(1) }} m³/h
        </strong>
      </div>
    </div>

    <el-dialog
      v-model="factorDialogVisible"
      :title="t('scheme.tower.factorDialogTitle')"
      width="420px"
      append-to-body
    >
      <el-form label-width="140px" size="small">
        <el-form-item :label="t('scheme.tower.factorLabel')">
          <NumberInput v-model="factorDraft" :min="0.10" :max="1.00" :step="0.01" :precision="2" />
        </el-form-item>
      </el-form>
      <div class="tower-factor-tip">{{ t('scheme.tower.factorTip') }}</div>
      <template #footer>
        <el-button @click="factorDialogVisible = false; factorDialogIndex = null">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="applyFactor">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

  </el-card>
</template>

<style scoped>
.tower-card {
  border: 0 !important;
  border-top: 1px solid var(--border-subtle) !important;
  border-radius: 0 !important;
  background: transparent;
  box-shadow: none !important;
  overflow: visible;
  padding-top: 14px;
}
.tower-card :deep(.el-card__header) {
  padding: 0 0 8px;
  border-bottom: 0;
}
.tower-card :deep(.el-card__body) { padding: 8px 0 0; }
.tower-head { display: flex; justify-content: space-between; align-items: center; }
.tower-head-actions { display: flex; align-items: center; gap: 6px; }
.tower-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}
.tower-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: #c2410c;
}
.tower-row {
  padding: 8px 0;
}
.tower-row + .tower-row {
  margin-top: 12px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}
.tower-block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.tower-block-head strong {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}
.tower-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
  margin-top: 8px;
}
.tower-summary-item {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  min-height: 28px;
}
.tower-summary-item + .tower-summary-item { border-left: 1px solid var(--border-subtle); }
.tower-summary-item span,
.tower-summary-item strong {
  padding: 6px 8px;
  font-size: 12px;
}
.tower-summary-item span {
  background: var(--surface-sunken);
  color: var(--text-secondary);
  font-weight: 500;
}
.tower-summary-item strong {
  color: var(--text-primary);
  font-weight: 500;
}
.tower-factor-tip { color: var(--text-muted); font-size: var(--font-size-xs); margin-top: -4px; }
.eq-detail {
  margin-top: 4px;
  padding: 2px 0;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: var(--line-height-normal);
  display: flex;
  flex-wrap: wrap;
  gap: 2px 8px;
}
.eq-detail span { white-space: nowrap; }
.eq-detail span:not(:last-child)::after {
  content: '·';
  color: var(--border-base);
  margin-left: 8px;
}
.eq-detail--warm span { color: #c2410c; }
.tower-row.has-error { background: var(--color-danger-soft); border-radius: var(--radius-md); padding: 6px 8px; }
.tower-issue { margin: 6px 0; }
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
  background: #fff7ed;
  color: #c2410c;
  font-size: 12px;
  font-weight: 500;
}
.device-cell strong {
  padding: 6px 8px;
  color: #c2410c;
  font-size: 12px;
  font-weight: 500;
  min-width: 0;
}

@media (max-width: 640px) {
  .tower-card {
    padding-top: 12px;
  }
  .tower-card :deep(.el-card__body) { padding: 6px 0 0; }
  .tower-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
  .tower-head-actions {
    width: 100%;
    justify-content: space-between;
  }
  .tower-block-head {
    flex-wrap: nowrap;
    align-items: center;
    gap: 6px;
  }
  .tower-block-head .tower-head-actions {
    width: auto;
    flex: 0 0 auto;
    gap: 4px;
  }
  .device-table,
  .tower-summary {
    grid-template-columns: minmax(0, 1fr);
  }
  .device-cell,
  .device-cell:nth-last-child(-n + 2),
  .tower-summary-item {
    grid-template-columns: 92px minmax(0, 1fr);
    border-bottom: 1px solid var(--border-subtle);
  }
  .device-cell:last-child,
  .tower-summary-item:last-child {
    border-bottom: 0;
  }
  .tower-summary-item + .tower-summary-item { border-left: 0; }
}

</style>
