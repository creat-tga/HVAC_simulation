<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
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
      <el-row :gutter="16">
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.chwSupplyTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.chw_supply_temp as number) ?? 7" :min="1" :max="25" :precision="1"
            @update:model-value="(v) => update('chw_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.chwDeltaTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.chw_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1"
            @update:model-value="(v) => update('chw_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.chwPumpHead')">
          <el-input-number value-on-clear="min" :model-value="(params.chw_pump_head as number) ?? 35" :min="1" :max="100" :precision="1"
            @update:model-value="(v) => update('chw_pump_head', v)" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.headerPressureDrop')">
          <el-input-number value-on-clear="min" :model-value="(params.header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1"
            @update:model-value="(v) => update('header_pressure_drop', v)" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.cwSupplyTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.cw_supply_temp as number) ?? 30" :min="1" :max="50" :precision="1"
            @update:model-value="(v) => update('cw_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.cwDeltaTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.cw_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1"
            @update:model-value="(v) => update('cw_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item :label="t('scheme.designParams.cwPumpHead')">
          <el-input-number value-on-clear="min" :model-value="(params.cw_pump_head as number) ?? 30" :min="1" :max="100" :precision="1"
            @update:model-value="(v) => update('cw_pump_head', v)" /></el-form-item></el-col>
      </el-row>
    </template>

    <!-- 风冷模块 -->
    <template v-else-if="schemeType === 'air_cooled'">
      <el-row :gutter="16">
        <el-col :span="6"><el-form-item :label="t('scheme.designParams.coolingSupplyTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.cooling_supply_temp as number) ?? 7" :min="1" :max="25" :precision="1"
            @update:model-value="(v) => update('cooling_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="6"><el-form-item :label="t('scheme.designParams.coolingDeltaTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.cooling_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1"
            @update:model-value="(v) => update('cooling_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="6"><el-form-item :label="t('scheme.designParams.heatingSupplyTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.heating_supply_temp as number) ?? 45" :min="30" :max="100" :precision="1"
            @update:model-value="(v) => update('heating_supply_temp', v)" /></el-form-item></el-col>
        <el-col :span="6"><el-form-item :label="t('scheme.designParams.heatingDeltaTemp')">
          <el-input-number value-on-clear="min" :model-value="(params.heating_delta_temp as number) ?? 5" :min="1" :max="15" :precision="1"
            @update:model-value="(v) => update('heating_delta_temp', v)" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item :label="t('scheme.designParams.pipeSystem')">
          <el-radio-group :model-value="pipeSystem" @update:model-value="(v) => update('pipe_system', v)">
            <el-radio-button value="two_pipe">{{ t('scheme.designParams.twoPipe') }}</el-radio-button>
            <el-radio-button value="four_pipe">{{ t('scheme.designParams.fourPipe') }}</el-radio-button>
          </el-radio-group>
        </el-form-item></el-col>
      </el-row>
      <template v-if="pipeSystem === 'two_pipe'">
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item :label="t('scheme.designParams.pumpHead')">
            <el-input-number value-on-clear="min" :model-value="(params.pump_head as number) ?? 35" :min="1" :max="100" :precision="1"
              @update:model-value="(v) => update('pump_head', v)" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item :label="t('scheme.designParams.headerPressureDrop')">
            <el-input-number value-on-clear="min" :model-value="(params.header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1"
              @update:model-value="(v) => update('header_pressure_drop', v)" /></el-form-item></el-col>
        </el-row>
      </template>
      <template v-else>
        <el-row :gutter="16">
          <el-col :span="6"><el-form-item :label="t('scheme.designParams.chwPumpHeadFour')">
            <el-input-number value-on-clear="min" :model-value="(params.chw_pump_head as number) ?? 35" :min="1" :max="100" :precision="1"
              @update:model-value="(v) => update('chw_pump_head', v)" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item :label="t('scheme.designParams.chwHeader')">
            <el-input-number value-on-clear="min" :model-value="(params.chw_header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1"
              @update:model-value="(v) => update('chw_header_pressure_drop', v)" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item :label="t('scheme.designParams.hwPumpHead')">
            <el-input-number value-on-clear="min" :model-value="(params.hw_pump_head as number) ?? 35" :min="1" :max="100" :precision="1"
              @update:model-value="(v) => update('hw_pump_head', v)" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item :label="t('scheme.designParams.hwHeader')">
            <el-input-number value-on-clear="min" :model-value="(params.hw_header_pressure_drop as number) ?? 21" :min="1" :max="100" :precision="1"
              @update:model-value="(v) => update('hw_header_pressure_drop', v)" /></el-form-item></el-col>
        </el-row>
      </template>
    </template>

    <template v-else>
      <el-empty description="共用冷却塔系统：待补充" :image-size="80" />
    </template>
  </el-card>
</template>

<style scoped>
.dp-card { border-radius: 12px; }
.dp-title { font-weight: 600; font-size: 15px; color: #0f172a; }
:deep(.el-form-item) { margin-bottom: 12px; }
:deep(.el-input-number) { width: 100%; }
</style>
