<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, Setting } from '@element-plus/icons-vue'
import EquipmentPicker from './EquipmentPicker.vue'
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
const factorDraft = ref(0.85)

function openFactorDialog() {
  factorDraft.value = groups.value[0]?.factor ?? 0.85
  factorDialogVisible.value = true
}

function applyFactor() {
  groups.value = groups.value.map((g) => ({ ...g, factor: factorDraft.value }))
  factorDialogVisible.value = false
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
        <span>{{ t('scheme.tower.title') }}</span>
        <div class="tower-head-actions">
          <el-button text size="small" :icon="Setting" @click="openFactorDialog">
            {{ t('scheme.combo.factorDialogBtn') }}
          </el-button>
          <el-button plain :icon="Plus" size="small" @click="add" :disabled="groups.length >= 10">
            {{ t('scheme.tower.add') }}
          </el-button>
        </div>
      </div>
    </template>

    <div v-for="(g, idx) in groups" :key="idx" class="tower-row" :class="{ 'has-error': towerIssues(idx).some((i) => i.severity === 'error') }">
      <strong>{{ t('scheme.tower.group') }} #{{ g.group_index }}</strong>
      <el-alert
        v-for="(iss, i) in towerIssues(idx)"
        :key="`tiss-${idx}-${i}`"
        :type="iss.severity === 'error' ? 'error' : 'warning'"
        :title="cleanMsg(iss.message)"
        show-icon
        :closable="false"
        class="tower-issue"
      />
      <el-row :gutter="10" align="middle">
        <el-col :span="10"><el-form-item :label="t('scheme.tower.model')">
          <EquipmentPicker
            :model-value="g.tower_model_id ?? null"
            equipment-type="cooling_tower"
            @update:model-value="(v) => onIdChange(idx, v)"
            @pick="onPicked"
          />
        </el-form-item></el-col>
        <el-col :span="4"><el-form-item :label="t('scheme.tower.count')">
          <el-input-number value-on-clear="min" v-model="g.count" :min="1" :max="20" size="small" /></el-form-item></el-col>
        <el-col :span="2">
          <el-button type="danger" :icon="Delete" text @click="remove(idx)" :disabled="groups.length <= 1" />
        </el-col>
      </el-row>

      <!-- 冷却塔参数表 -->
      <el-descriptions
        v-if="derived?.tower_groups?.[idx] && g.tower_model_id"
        :column="2"
        size="small"
        border
        class="device-table device-table--warm"
      >
        <el-descriptions-item :label="t('scheme.derived.flowLabel')">
          {{ unitVal(derived.tower_groups[idx].flow, derived.tower_groups[idx].count) }} × {{ derived.tower_groups[idx].count }} = {{ derived.tower_groups[idx].flow }} m³/h
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.headLabel')">
          {{ derived.tower_groups[idx].head }} mH₂O
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.derived.powerLabel')">
          {{ unitVal(derived.tower_groups[idx].power, derived.tower_groups[idx].count) }} × {{ derived.tower_groups[idx].count }} = {{ derived.tower_groups[idx].power }} kW
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.tower.inletTemp')">
          {{ derived.tower_groups[idx].inlet_temp }} ℃
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.tower.outletTemp')">
          {{ derived.tower_groups[idx].outlet_temp }} ℃
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.tower.wetBulb')">
          {{ derived.tower_groups[idx].wet_bulb }} ℃
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-if="derived" class="tower-summary">
      <el-descriptions :column="2" size="small" border>
        <el-descriptions-item :label="t('scheme.tower.flowRequired')">
          {{ requiredFlow.toFixed(1) }} m³/h
        </el-descriptions-item>
        <el-descriptions-item :label="t('scheme.tower.flowSupply')">
          <span :style="{ color: Math.abs(supplyFlow - requiredFlow) / Math.max(requiredFlow, 1) > 0.1 ? 'var(--color-danger)' : 'var(--color-success)' }">
            {{ supplyFlow.toFixed(1) }} m³/h
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <el-dialog
      v-model="factorDialogVisible"
      :title="t('scheme.tower.factorDialogTitle')"
      width="420px"
      append-to-body
    >
      <el-form label-width="140px" size="small">
        <el-form-item :label="t('scheme.tower.factorLabel')">
          <el-input-number
            v-model="factorDraft"
            value-on-clear="min"
            :min="0.10"
            :max="1.00"
            :step="0.01"
            :precision="2"
          />
        </el-form-item>
      </el-form>
      <div class="tower-factor-tip">{{ t('scheme.tower.factorTip') }}</div>
      <template #footer>
        <el-button @click="factorDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="applyFactor">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

  </el-card>
</template>

<style scoped>
.tower-card { border-radius: var(--radius-lg); }
.tower-head { display: flex; justify-content: space-between; align-items: center; }
.tower-head-actions { display: flex; align-items: center; gap: 6px; }
.tower-row { padding: 8px 0; }
.tower-row :deep(.el-input-number) { width: 100%; }
.tower-row :deep(.el-input) { width: 100%; }
.tower-summary { margin-top: 8px; }
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
.tower-issue { margin: 8px 0; }
.device-table { margin: 4px 0 12px 0; }
.device-table :deep(.el-descriptions__label) { width: 110px; }
.device-table--warm :deep(.el-descriptions__label) { background: #fff7ed; color: #c2410c; }
.device-table--warm :deep(.el-descriptions__content) { color: #c2410c; }
</style>
