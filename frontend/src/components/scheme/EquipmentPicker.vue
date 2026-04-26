<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEquipmentLibraryStore } from '@/stores/equipment-library'
import type { EquipmentBrief, EquipmentSearchParams } from '@/types/system-scheme'

const { t } = useI18n()

const props = defineProps<{
  modelValue?: string | null
  equipmentType: EquipmentSearchParams['equipment_type']
  cachedLabel?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [v: string | null]
  pick: [eq: EquipmentBrief]
}>()

const store = useEquipmentLibraryStore()

const value = computed({
  get: () => props.modelValue ?? null,
  set: (v) => emit('update:modelValue', v),
})

const query = ref('')

const filter = reactive({
  capacity_min: undefined as number | undefined,
  capacity_max: undefined as number | undefined,
  flow_min: undefined as number | undefined,
  flow_max: undefined as number | undefined,
  head_min: undefined as number | undefined,
  head_max: undefined as number | undefined,
  efficiency_min: undefined as number | undefined,
  efficiency_max: undefined as number | undefined,
})

const showCapacity = computed(
  () => props.equipmentType === 'chiller' || props.equipmentType === 'air_cooled_module',
)
const showFlow = computed(
  () => props.equipmentType === 'pump' || props.equipmentType === 'cooling_tower',
)
const showHeadEff = computed(() => props.equipmentType === 'pump')

function rangeInvalid(min: number | undefined, max: number | undefined): boolean {
  return min !== undefined && max !== undefined && Number(min) > Number(max)
}
const invalidRanges = computed(() => {
  const issues: string[] = []
  if (showCapacity.value && rangeInvalid(filter.capacity_min, filter.capacity_max))
    issues.push(t('scheme.equipmentSearch.capacityRange'))
  if (showFlow.value && rangeInvalid(filter.flow_min, filter.flow_max))
    issues.push(t('scheme.equipmentSearch.flowRange'))
  if (showHeadEff.value && rangeInvalid(filter.head_min, filter.head_max))
    issues.push(t('scheme.equipmentSearch.headRange'))
  if (showHeadEff.value && rangeInvalid(filter.efficiency_min, filter.efficiency_max))
    issues.push(t('scheme.equipmentSearch.efficiencyRange'))
  return issues
})
const hasInvalidRange = computed(() => invalidRanges.value.length > 0)

const loading = computed(() => store.isLoading(props.equipmentType))
function ensureLoaded() {
  if (!store.cache[props.equipmentType]) {
    void store.load(props.equipmentType)
  }
}
// 不在挂载时立即拉取设备库；仅在用户首次打开 popup（@visible-change）
// 或 modelValue 已有但缓存缺失（下方 watch）时才加载，
// 避免子系统首次展开时 N 个 EquipmentPicker 同时触发请求与解析阻塞。

function paramNum(eq: EquipmentBrief, key: string): number {
  const v = (eq.parameters as Record<string, unknown> | null)?.[key]
  return typeof v === 'number' ? v : Number(v) || 0
}

const filtered = computed<EquipmentBrief[]>(() => {
  const all = store.get(props.equipmentType)
  if (!all.length) return []
  const kw = query.value.trim().toLowerCase()
  // Skip range filters that are invalid; treat them as ignored rather than freezing.
  const useCap = showCapacity.value && !rangeInvalid(filter.capacity_min, filter.capacity_max)
  const useFlow = showFlow.value && !rangeInvalid(filter.flow_min, filter.flow_max)
  const useHead = showHeadEff.value && !rangeInvalid(filter.head_min, filter.head_max)
  const useEff = showHeadEff.value && !rangeInvalid(filter.efficiency_min, filter.efficiency_max)

  return all.filter((eq) => {
    if (kw) {
      const hay = `${eq.brand || ''} ${eq.model_no || ''} ${eq.name || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    if (useCap) {
      const cap = Number(eq.capacity || 0)
      if (filter.capacity_min !== undefined && cap < filter.capacity_min) return false
      if (filter.capacity_max !== undefined && cap > filter.capacity_max) return false
    }
    if (useFlow) {
      const flow = paramNum(eq, 'flow')
      if (filter.flow_min !== undefined && flow < filter.flow_min) return false
      if (filter.flow_max !== undefined && flow > filter.flow_max) return false
    }
    if (useHead) {
      const head = paramNum(eq, 'head')
      if (filter.head_min !== undefined && head < filter.head_min) return false
      if (filter.head_max !== undefined && head > filter.head_max) return false
    }
    if (useEff) {
      const eff = paramNum(eq, 'efficiency')
      if (filter.efficiency_min !== undefined && eff < filter.efficiency_min) return false
      if (filter.efficiency_max !== undefined && eff > filter.efficiency_max) return false
    }
    return true
  })
})
const selectedEq = computed(() => (props.modelValue ? store.findById(props.modelValue) : undefined))

// el-select-v2 需要 options 数组；其虚拟滚动可一次性接收上千条选项。
const v2Options = computed(() => {
  const list = filtered.value.map((eq) => ({
    value: eq.id,
    label: fmtLabel(eq),
    eq,
  }))
  // 如果当前选中项不在过滤后的列表里，补上以位首。
  const sel = selectedEq.value
  if (sel && !list.some((o) => o.value === sel.id)) {
    list.unshift({ value: sel.id, label: fmtLabel(sel), eq: sel })
  }
  return list
})

function onRemote(q: string) {
  query.value = q
}

function resetFilter() {
  filter.capacity_min = undefined
  filter.capacity_max = undefined
  filter.flow_min = undefined
  filter.flow_max = undefined
  filter.head_min = undefined
  filter.head_max = undefined
  filter.efficiency_min = undefined
  filter.efficiency_max = undefined
  query.value = ''
}

function onChange(id: string | null) {
  value.value = id
  if (id) {
    const eq = store.findById(id)
    if (eq) emit('pick', eq)
  }
}

function fmtLabel(eq: EquipmentBrief): string {
  // 选型列表中不包含厂家（品牌），只显示型号 / 名称。
  return (eq.model_no || eq.name || '').trim()
}

function fmt1(n: unknown): string {
  const v = Number(n)
  if (!isFinite(v)) return ''
  return (Math.round(v * 10) / 10).toString()
}

watch(
  () => props.modelValue,
  (id) => {
    if (id && !store.findById(id)) ensureLoaded()
  },
  { immediate: true },
)
</script>

<template>
  <el-select-v2
    v-model="value"
    :options="v2Options"
    filterable
    remote
    clearable
    size="small"
    :remote-method="onRemote"
    :loading="loading"
    :placeholder="t('scheme.combo.pleasePick')"
    class="eq-picker-select"
    popper-class="eq-picker-popper"
    :item-height="40"
    :height="320"
    @change="onChange"
    @visible-change="(v: boolean) => v && ensureLoaded()"
  >
    <template #header>
      <div class="eq-filter">
        <template v-if="showCapacity">
          <span class="eq-filter-label">{{ t('scheme.equipmentSearch.capacityRange') }}</span>
          <el-input-number
            v-model="filter.capacity_min"
            placeholder="-"
            :min="0"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
          <span class="eq-filter-sep">~</span>
          <el-input-number
            v-model="filter.capacity_max"
            placeholder="-"
            :min="0"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
        </template>
        <template v-if="showFlow">
          <span class="eq-filter-label">{{ t('scheme.equipmentSearch.flowRange') }}</span>
          <el-input-number
            v-model="filter.flow_min"
            placeholder="-"
            :min="0"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
          <span class="eq-filter-sep">~</span>
          <el-input-number
            v-model="filter.flow_max"
            placeholder="-"
            :min="0"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
        </template>
        <template v-if="showHeadEff">
          <span class="eq-filter-label">{{ t('scheme.equipmentSearch.headRange') }}</span>
          <el-input-number
            v-model="filter.head_min"
            placeholder="-"
            :min="0"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
          <span class="eq-filter-sep">~</span>
          <el-input-number
            v-model="filter.head_max"
            placeholder="-"
            :min="0"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
          <span class="eq-filter-label">{{ t('scheme.equipmentSearch.efficiencyRange') }}</span>
          <el-input-number
            v-model="filter.efficiency_min"
            placeholder="-"
            :min="0"
            :max="1"
            :step="0.05"
            :precision="2"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
          <span class="eq-filter-sep">~</span>
          <el-input-number
            v-model="filter.efficiency_max"
            placeholder="-"
            :min="0"
            :max="1"
            :step="0.05"
            :precision="2"
            :controls="false"
            size="small"
            class="eq-range-input"
          />
        </template>
        <el-button text size="small" class="eq-filter-reset" @click="resetFilter">
          {{ t('common.reset') }}
        </el-button>
      </div>
      <div v-if="hasInvalidRange" class="eq-filter-warn">
        {{ t('scheme.equipmentSearch.rangeInvalid', { fields: invalidRanges.join('、') }) }}
      </div>
    </template>

    <template #default="{ item }">
      <div class="eq-opt">
        <span class="eq-opt-main">{{ item.label }}</span>
        <span class="eq-opt-sub">
          <span v-if="item.eq.capacity">{{ fmt1(item.eq.capacity) }} kW</span>
          <span v-if="(item.eq.parameters as any)?.flow">· {{ fmt1((item.eq.parameters as any).flow) }} m³/h</span>
          <span v-if="(item.eq.parameters as any)?.head">· {{ fmt1((item.eq.parameters as any).head) }} mH₂O</span>
        </span>
      </div>
    </template>

    <template #empty>
      <div class="eq-empty">
        <el-empty :description="t('scheme.equipmentSearch.noResult')" :image-size="60" />
      </div>
    </template>
  </el-select-v2>
</template>

<style scoped>
.eq-picker-select {
  width: var(--scheme-control-width, 150px);
}
.eq-picker-select :deep(.el-select__wrapper) {
  min-height: var(--scheme-control-height, 24px);
  height: var(--scheme-control-height, 24px);
  padding: 0 8px;
  display: flex;
  align-items: center;
  line-height: var(--scheme-control-height, 24px);
}
.eq-picker-select :deep(.el-select__selection) {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1 1 auto;
  min-width: 0;
  line-height: var(--scheme-control-height, 24px);
  text-align: center;
}
.eq-picker-select :deep(.el-select__placeholder),
.eq-picker-select :deep(.el-select__selected-item),
.eq-picker-select :deep(.el-select__selected-item span) {
  line-height: var(--scheme-control-height, 24px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  width: 100%;
}
.eq-opt {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-width: 0;
  line-height: 1.4;
}
.eq-opt-main {
  flex: 0 1 auto;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.eq-opt-sub {
  color: #94a3b8;
  font-size: 12px;
  flex: 0 0 auto;
  white-space: nowrap;
}
.eq-empty {
  padding: 8px 0;
}
</style>

<style>
.eq-picker-popper .eq-filter {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}
.eq-picker-popper .eq-filter-label {
  font-size: 12px;
  color: #475569;
  margin-left: 4px;
}
.eq-picker-popper .eq-filter-sep {
  color: #94a3b8;
}
.eq-picker-popper .eq-filter-reset {
  margin-left: auto;
}
.eq-picker-popper .eq-range-input {
  width: 78px !important;
}
.eq-picker-popper .eq-range-input .el-input__wrapper {
  padding: 0 6px;
}
.eq-picker-popper .eq-range-input .el-input__inner {
  text-align: center;
}
.eq-picker-popper .eq-filter-warn {
  padding: 4px 12px 6px;
  font-size: 12px;
  color: #d97706;
  background: #fffbeb;
  border-bottom: 1px solid #fde68a;
}
/* 强制下拉面板最小宽度，避免被狭窄的输入框限制后选项被截断。
   最终宽度 = max(输入框宽度, 360px)。 */
.eq-picker-popper {
  min-width: 360px !important;
  width: 360px !important;
}
.eq-picker-popper .el-select-dropdown,
.eq-picker-popper .el-vl__wrapper,
.eq-picker-popper .el-vl__window {
  min-width: 360px !important;
  width: 360px !important;
}
.eq-picker-popper .eq-opt {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  white-space: nowrap;
  overflow: hidden;
}
.eq-picker-popper .eq-opt-main {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}
.eq-picker-popper .eq-opt-sub {
  flex: 0 0 auto;
  color: #94a3b8;
  font-size: 12px;
}
.eq-picker-popper .eq-opt-sub > span {
  margin-left: 4px;
}
</style>
