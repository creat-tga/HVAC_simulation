<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import NumberInput from './NumberInput.vue'
import type { SubsystemType } from '@/types/system-scheme'

const { t } = useI18n()

const props = defineProps<{
  modelValue: Record<string, unknown>
  schemeType: SubsystemType
}>()
const emit = defineEmits<{ 'update:modelValue': [v: Record<string, unknown>] }>()

const params = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function update<K extends string>(key: K, val: unknown) {
  params.value = { ...params.value, [key]: val }
}

const pipeSystem = computed(() => (params.value.pipe_system as string) || 'two_pipe')
</script>

<template>
  <el-card shadow="never" class="dp-card">
    <template #header>
      <div class="dp-title">{{ t('scheme.designParams.title') }}</div>
    </template>

    <!-- 制冷机房 -->
    <template v-if="schemeType === 'chiller_plant'">
      <el-row :gutter="8" class="dp-grid scheme-field-grid">
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.chwSupplyTemp')">
          <NumberInput :model-value="(params.chw_supply_temp as number) ?? 7" :min="1" :max="25" :precision="1" @update:model-value="(v) => update('chw_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.chwDeltaTemp')">
          <NumberInput :model-value="(params.chw_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1" @update:model-value="(v) => update('chw_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.chwPumpHead')">
          <NumberInput :model-value="(params.chw_pump_head as number) ?? 35" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('chw_pump_head', v)" /></el-form-item></el-col>
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.headerPressureDrop')">
          <NumberInput :model-value="(params.header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('header_pressure_drop', v)" /></el-form-item></el-col>
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.cwSupplyTemp')">
          <NumberInput :model-value="(params.cw_supply_temp as number) ?? 30" :min="1" :max="50" :precision="1" @update:model-value="(v) => update('cw_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.cwDeltaTemp')">
          <NumberInput :model-value="(params.cw_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1" @update:model-value="(v) => update('cw_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.cwPumpHead')">
          <NumberInput :model-value="(params.cw_pump_head as number) ?? 30" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('cw_pump_head', v)" /></el-form-item></el-col>
      </el-row>
    </template>

    <!-- 风冷模块 -->
    <template v-else-if="schemeType === 'air_cooled'">
      <el-row :gutter="8" class="dp-grid dp-grid--air scheme-field-grid">
        <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.coolingSupplyTemp')">
          <NumberInput :model-value="(params.cooling_supply_temp as number) ?? 7" :min="1" :max="25" :precision="1" @update:model-value="(v) => update('cooling_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.coolingDeltaTemp')">
          <NumberInput :model-value="(params.cooling_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1" @update:model-value="(v) => update('cooling_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.heatingSupplyTemp')">
          <NumberInput :model-value="(params.heating_supply_temp as number) ?? 45" :min="30" :max="100" :precision="1" @update:model-value="(v) => update('heating_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.heatingDeltaTemp')">
          <NumberInput :model-value="(params.heating_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1" @update:model-value="(v) => update('heating_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="12" class="scheme-field-col scheme-field-col--radio"><el-form-item class="scheme-field-item--auto" :label="t('scheme.designParams.pipeSystem')">
          <el-radio-group :model-value="pipeSystem" size="small" @update:model-value="(v) => update('pipe_system', v)">
            <el-radio value="two_pipe">{{ t('scheme.designParams.twoPipe') }}</el-radio>
            <el-radio value="four_pipe">{{ t('scheme.designParams.fourPipe') }}</el-radio>
          </el-radio-group>
        </el-form-item></el-col>
      </el-row>
      <template v-if="pipeSystem === 'two_pipe'">
        <el-row :gutter="8" class="dp-grid scheme-field-grid">
          <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.pumpHead')">
            <NumberInput :model-value="(params.pump_head as number) ?? 35" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('pump_head', v)" /></el-form-item></el-col>
          <el-col :span="8" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.headerPressureDrop')">
            <NumberInput :model-value="(params.header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('header_pressure_drop', v)" /></el-form-item></el-col>
        </el-row>
      </template>
      <template v-else>
        <el-row :gutter="8" class="dp-grid dp-grid--air scheme-field-grid">
          <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.chwPumpHeadFour')">
            <NumberInput :model-value="(params.chw_pump_head as number) ?? 35" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('chw_pump_head', v)" /></el-form-item></el-col>
          <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.chwHeader')">
            <NumberInput :model-value="(params.chw_header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('chw_header_pressure_drop', v)" /></el-form-item></el-col>
          <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.hwPumpHead')">
            <NumberInput :model-value="(params.hw_pump_head as number) ?? 35" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('hw_pump_head', v)" /></el-form-item></el-col>
          <el-col :span="6" class="scheme-field-col"><el-form-item :label="t('scheme.designParams.hwHeader')">
            <NumberInput :model-value="(params.hw_header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1" @update:model-value="(v) => update('hw_header_pressure_drop', v)" /></el-form-item></el-col>
        </el-row>
      </template>
    </template>

    <template v-else>
      <el-empty description="共用冷却塔系统：待补充" :image-size="80" />
    </template>
  </el-card>
</template>

<style scoped>
.dp-card {
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent;
  box-shadow: none !important;
  overflow: visible;
}
.dp-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}
.dp-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: #2563eb;
}
.dp-card :deep(.el-card__header) {
  padding: 0 0 8px;
  border-bottom: 0;
}
.dp-card :deep(.el-card__body) { padding: 8px 0 0; }
:deep(.el-radio-group) { flex-wrap: nowrap; }
:deep(.el-radio-button__inner) { padding: 5px 10px; }

@media (max-width: 640px) {
  .dp-card :deep(.el-card__body) { padding: 6px 0 0; }
}

</style>
