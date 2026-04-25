<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { StrategyProfileMode, StrategyValueProfile } from '@/types/system-scheme'

const props = withDefaults(defineProps<{
  modelValue: StrategyValueProfile
  label: string
  unit?: string
  min?: number
  max?: number
  step?: number
  allowConstantPressure?: boolean
}>(), {
  unit: '℃',
  min: 0,
  max: 100,
  step: 0.1,
  allowConstantPressure: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: StrategyValueProfile): void
}>()

const { t } = useI18n()

const modeOptions = computed(() => {
  const base: Array<{ label: string; value: StrategyProfileMode }> = [
    { label: t('scheme.strategy.modes.fixed'), value: 'fixed' },
    { label: t('scheme.strategy.modes.by_month'), value: 'by_month' },
    { label: t('scheme.strategy.modes.by_load'), value: 'by_load' },
    { label: t('scheme.strategy.modes.by_dry_bulb'), value: 'by_dry_bulb' },
    { label: t('scheme.strategy.modes.by_wet_bulb'), value: 'by_wet_bulb' },
  ]
  if (props.allowConstantPressure) {
    base.push({ label: t('scheme.strategy.modes.constant_pressure'), value: 'constant_pressure' })
  }
  return base
})

const mode = computed({
  get: () => props.modelValue.mode,
  set: (value) => emit('update:modelValue', { ...props.modelValue, mode: value }),
})

const fixedValue = computed({
  get: () => props.modelValue.fixed_value,
  set: (value) => emit('update:modelValue', { ...props.modelValue, fixed_value: value }),
})

function patchArray(key: 'month_values' | 'load_values' | 'dry_bulb_values' | 'wet_bulb_values', idx: number, value: number) {
  const next = [...props.modelValue[key]]
  next[idx] = value
  emit('update:modelValue', { ...props.modelValue, [key]: next })
}

const monthLabels = Array.from({ length: 12 }, (_, idx) => `${idx + 1}月`)
const loadLabels = ['0~10%', '10~20%', '20~30%', '30~40%', '40~50%', '50~60%', '60~70%', '70~80%', '80~90%', '90~100%', '100%']
const dryBulbLabels = ['<10℃', '10~15℃', '15~20℃', '20~25℃', '25~30℃', '30~35℃', '35~40℃', '40~45℃', '45~50℃', '>50℃']
const wetBulbLabels = ['<10℃', '10~15℃', '15~20℃', '20~25℃', '25~30℃', '30~35℃', '35~40℃', '40~45℃', '45~50℃', '>50℃']
</script>

<template>
  <div class="profile-card">
    <div class="profile-head">
      <div class="profile-head-left">
        <span class="profile-label">{{ label }}</span>
        <span class="profile-unit">({{ unit }})</span>
      </div>
      <el-select v-model="mode" size="small" class="profile-mode">
        <el-option v-for="item in modeOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </div>

    <div v-if="mode === 'fixed'" class="profile-fixed">
      <el-input-number v-model="fixedValue" :min="min" :max="max" :step="step" :precision="2" controls-position="right" size="small" />
    </div>

    <div v-else-if="mode === 'constant_pressure'" class="profile-tip">
      <el-tag type="warning" size="small">{{ t('scheme.strategy.modes.constant_pressure') }}</el-tag>
    </div>

    <div v-else class="profile-grid">
      <template v-if="mode === 'by_month'">
        <div v-for="(item, idx) in monthLabels" :key="item" class="profile-cell">
          <div class="profile-cell-label">{{ item }}</div>
          <el-input-number
            :model-value="modelValue.month_values[idx]"
            :min="min"
            :max="max"
            :step="step"
            :precision="2"
            controls-position="right"
            size="small"
            @update:model-value="(val) => patchArray('month_values', idx, Number(val || 0))"
          />
        </div>
      </template>

      <template v-else-if="mode === 'by_load'">
        <div v-for="(item, idx) in loadLabels" :key="item" class="profile-cell">
          <div class="profile-cell-label">{{ item }}</div>
          <el-input-number
            :model-value="modelValue.load_values[idx]"
            :min="min"
            :max="max"
            :step="step"
            :precision="2"
            controls-position="right"
            size="small"
            @update:model-value="(val) => patchArray('load_values', idx, Number(val || 0))"
          />
        </div>
      </template>

      <template v-else-if="mode === 'by_dry_bulb'">
        <div v-for="(item, idx) in dryBulbLabels" :key="item" class="profile-cell">
          <div class="profile-cell-label">{{ item }}</div>
          <el-input-number
            :model-value="modelValue.dry_bulb_values[idx]"
            :min="min"
            :max="max"
            :step="step"
            :precision="2"
            controls-position="right"
            size="small"
            @update:model-value="(val) => patchArray('dry_bulb_values', idx, Number(val || 0))"
          />
        </div>
      </template>

      <template v-else>
        <div v-for="(item, idx) in wetBulbLabels" :key="item" class="profile-cell">
          <div class="profile-cell-label">{{ item }}</div>
          <el-input-number
            :model-value="modelValue.wet_bulb_values[idx]"
            :min="min"
            :max="max"
            :step="step"
            :precision="2"
            controls-position="right"
            size="small"
            @update:model-value="(val) => patchArray('wet_bulb_values', idx, Number(val || 0))"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.profile-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  background: #fff;
}
.profile-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.profile-head-left {
  display: flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
}
.profile-label {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}
.profile-unit {
  font-size: 11px;
  color: #94a3b8;
}
.profile-mode {
  width: 140px;
  flex-shrink: 0;
}
.profile-fixed {
  display: flex;
  align-items: center;
  gap: 8px;
}
.profile-tip {
  display: flex;
  align-items: center;
  gap: 8px;
}
.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
  gap: 4px;
}
.profile-cell {
  padding: 4px 6px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  min-width: 0;
}
.profile-cell-label {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.profile-cell :deep(.el-input-number) {
  width: 100%;
}
.profile-cell :deep(.el-input-number .el-input__wrapper) {
  padding: 0 4px;
}
.profile-cell :deep(.el-input-number .el-input__inner) {
  text-align: left;
  font-size: 12px;
}
</style>
