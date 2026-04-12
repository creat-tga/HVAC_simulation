<script setup lang="ts">
import { reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { HVACSystemCreate, HVACSystem } from '@/types/simulation'

const { t } = useI18n()

const props = defineProps<{
  initialData?: HVACSystem | null
}>()

const emit = defineEmits<{
  submit: [data: HVACSystemCreate]
  cancel: []
}>()

const form = reactive({
  system_type: '',
  name: '',
  capacity: 500 as number | undefined,
  cop: 5.0 as number | undefined,
  // Equipment — efficient_chiller_plant specific
  chillers: [{ cooling_capacity: 500, cop: 5.5, power: 90.9, count: 2 }],
  chw_pumps: [{ flow: 100, head: 25, power: 15, count: 2 }],
  cw_pumps: [{ flow: 120, head: 20, power: 12, count: 2 }],
  cooling_towers: [{ flow: 120, fan_power: 7.5, approach_temp: 4, count: 2 }],
  // Strategies
  chiller_staging: { loading_up: 85, loading_down: 30 },
  chw_pump_strategy: { type: 'constant_temp_diff' as string, setpoint: 5 },
  cw_pump_strategy: { type: 'constant_pressure_diff' as string, setpoint: 50 },
  cooling_tower_approach: 4,
})

const systemTypes = [
  { value: 'efficient_chiller_plant', label: t('system.types.efficient_chiller_plant') },
  { value: 'air_cooled_system', label: t('system.types.air_cooled_system') },
  { value: 'gshp_system', label: t('system.types.gshp_system') },
]

const pumpStrategyTypes = [
  { value: 'constant_temp_diff', label: t('system.strategy.constantTempDiff') },
  { value: 'constant_pressure_diff', label: t('system.strategy.constantPressureDiff') },
]

const showChillerPlant = computed(() => form.system_type === 'efficient_chiller_plant')

onMounted(() => {
  if (props.initialData) {
    const d = props.initialData
    form.system_type = d.system_type
    form.name = d.name
    form.capacity = d.capacity ?? 500
    form.cop = d.cop ?? 5.0
    const params = d.parameters || {}
    const equipment = params.equipment as Record<string, unknown[]> | undefined
    if (equipment) {
      if (equipment.chillers) form.chillers = equipment.chillers as typeof form.chillers
      if (equipment.chw_pumps) form.chw_pumps = equipment.chw_pumps as typeof form.chw_pumps
      if (equipment.cw_pumps) form.cw_pumps = equipment.cw_pumps as typeof form.cw_pumps
      if (equipment.cooling_towers) form.cooling_towers = equipment.cooling_towers as typeof form.cooling_towers
    }
    const strategies = params.strategies as Record<string, unknown> | undefined
    if (strategies) {
      if (strategies.chiller_staging) form.chiller_staging = strategies.chiller_staging as typeof form.chiller_staging
      if (strategies.chw_pump) form.chw_pump_strategy = strategies.chw_pump as typeof form.chw_pump_strategy
      if (strategies.cw_pump) form.cw_pump_strategy = strategies.cw_pump as typeof form.cw_pump_strategy
      if (strategies.cooling_tower_approach != null) form.cooling_tower_approach = strategies.cooling_tower_approach as number
    }
  }
})

watch(() => form.system_type, (type) => {
  if (type === 'efficient_chiller_plant') {
    form.cop = 5.5
    form.name = t('system.types.efficient_chiller_plant')
  } else if (type === 'air_cooled_system') {
    form.cop = 3.2
    form.name = t('system.types.air_cooled_system')
  } else if (type === 'gshp_system') {
    form.cop = 5.5
    form.name = t('system.types.gshp_system')
  }
})

function handleSubmit() {
  const parameters: Record<string, unknown> = {}

  if (form.system_type === 'efficient_chiller_plant') {
    parameters.equipment = {
      chillers: form.chillers,
      chw_pumps: form.chw_pumps,
      cw_pumps: form.cw_pumps,
      cooling_towers: form.cooling_towers,
    }
    parameters.strategies = {
      chiller_staging: form.chiller_staging,
      chw_pump: form.chw_pump_strategy,
      cw_pump: form.cw_pump_strategy,
      cooling_tower_approach: form.cooling_tower_approach,
    }
    // Sum up auxiliary ratio from pumps/towers
    const totalChillerPower = form.chillers.reduce((s, c) => s + c.power * c.count, 0)
    const totalPumpPower = form.chw_pumps.reduce((s, p) => s + p.power * p.count, 0)
      + form.cw_pumps.reduce((s, p) => s + p.power * p.count, 0)
      + form.cooling_towers.reduce((s, ct) => s + ct.fan_power * ct.count, 0)
    parameters.auxiliary_ratio = totalChillerPower > 0 ? +(totalPumpPower / totalChillerPower).toFixed(3) : 0.3
  } else if (form.system_type === 'air_cooled_system') {
    parameters.heating_cop = 3.0
  } else if (form.system_type === 'gshp_system') {
    parameters.heating_cop = 4.0
    parameters.pump_power_ratio = 0.15
  }

  emit('submit', {
    system_type: form.system_type,
    name: form.name,
    capacity: form.capacity,
    cop: form.cop,
    parameters,
  })
}
</script>

<template>
  <div class="system-config">
    <el-form :model="form" label-width="140px">
      <!-- Basic info -->
      <el-form-item :label="t('system.type')" required>
        <el-select v-model="form.system_type" :placeholder="t('system.pleaseSelectType')" style="width: 100%">
          <el-option v-for="s in systemTypes" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('system.name')" required>
        <el-input v-model="form.name" :placeholder="t('system.pleaseInputName')" />
      </el-form-item>
      <el-form-item :label="t('system.capacity')">
        <el-input-number v-model="form.capacity" :min="0" :precision="1" style="width: 200px" />
      </el-form-item>
      <el-form-item label="COP" v-if="form.system_type !== ''">
        <el-input-number v-model="form.cop" :min="0" :precision="2" :step="0.1" style="width: 200px" />
      </el-form-item>

      <!-- Equipment Selection (only for efficient_chiller_plant) -->
      <template v-if="showChillerPlant">
        <el-divider>{{ t('system.equipment.title') }}</el-divider>

        <!-- Chillers -->
        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.equipment.chillerTitle') }}</template>
          <div v-for="(chiller, idx) in form.chillers" :key="idx" class="equipment-row">
            <el-form-item :label="t('system.equipment.coolingCapacity')">
              <el-input-number v-model="chiller.cooling_capacity" :min="0" :precision="0" size="small" />
            </el-form-item>
            <el-form-item label="COP">
              <el-input-number v-model="chiller.cop" :min="0" :precision="2" :step="0.1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.power')">
              <el-input-number v-model="chiller.power" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.count')">
              <el-input-number v-model="chiller.count" :min="1" :max="10" size="small" />
            </el-form-item>
          </div>
        </el-card>

        <!-- CHW Pumps -->
        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.equipment.chwPumpTitle') }}</template>
          <div v-for="(pump, idx) in form.chw_pumps" :key="idx" class="equipment-row">
            <el-form-item :label="t('system.equipment.flow')">
              <el-input-number v-model="pump.flow" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.head')">
              <el-input-number v-model="pump.head" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.power')">
              <el-input-number v-model="pump.power" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.count')">
              <el-input-number v-model="pump.count" :min="1" :max="10" size="small" />
            </el-form-item>
          </div>
        </el-card>

        <!-- CW Pumps -->
        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.equipment.cwPumpTitle') }}</template>
          <div v-for="(pump, idx) in form.cw_pumps" :key="idx" class="equipment-row">
            <el-form-item :label="t('system.equipment.flow')">
              <el-input-number v-model="pump.flow" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.head')">
              <el-input-number v-model="pump.head" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.power')">
              <el-input-number v-model="pump.power" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.count')">
              <el-input-number v-model="pump.count" :min="1" :max="10" size="small" />
            </el-form-item>
          </div>
        </el-card>

        <!-- Cooling Towers -->
        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.equipment.coolingTowerTitle') }}</template>
          <div v-for="(tower, idx) in form.cooling_towers" :key="idx" class="equipment-row">
            <el-form-item :label="t('system.equipment.flow')">
              <el-input-number v-model="tower.flow" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.fanPower')">
              <el-input-number v-model="tower.fan_power" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.approachTemp')">
              <el-input-number v-model="tower.approach_temp" :min="0" :precision="1" size="small" />
            </el-form-item>
            <el-form-item :label="t('system.equipment.count')">
              <el-input-number v-model="tower.count" :min="1" :max="10" size="small" />
            </el-form-item>
          </div>
        </el-card>

        <!-- Strategy Configuration -->
        <el-divider>{{ t('system.strategy.title') }}</el-divider>

        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.strategy.chillerStaging') }}</template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="t('system.strategy.loadingUp')">
                <el-input-number v-model="form.chiller_staging.loading_up" :min="50" :max="100" size="small" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('system.strategy.loadingDown')">
                <el-input-number v-model="form.chiller_staging.loading_down" :min="10" :max="50" size="small" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-card>

        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.strategy.chwPumpStrategy') }}</template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="t('system.strategy.strategyType')">
                <el-select v-model="form.chw_pump_strategy.type" size="small">
                  <el-option v-for="s in pumpStrategyTypes" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item
                :label="form.chw_pump_strategy.type === 'constant_temp_diff' ? t('system.strategy.tempDiffSetpoint') : t('system.strategy.pressureDiffSetpoint')"
              >
                <el-input-number v-model="form.chw_pump_strategy.setpoint" :min="0" :precision="1" size="small" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-card>

        <el-card shadow="never" class="equipment-card">
          <template #header>{{ t('system.strategy.cwPumpStrategy') }}</template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="t('system.strategy.strategyType')">
                <el-select v-model="form.cw_pump_strategy.type" size="small">
                  <el-option v-for="s in pumpStrategyTypes" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item
                :label="form.cw_pump_strategy.type === 'constant_temp_diff' ? t('system.strategy.tempDiffSetpoint') : t('system.strategy.pressureDiffSetpoint')"
              >
                <el-input-number v-model="form.cw_pump_strategy.setpoint" :min="0" :precision="1" size="small" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-card>

        <el-form-item :label="t('system.strategy.coolingTowerApproach')">
          <el-input-number v-model="form.cooling_tower_approach" :min="1" :max="10" :precision="1" />
        </el-form-item>
      </template>

      <el-form-item>
        <el-button type="primary" @click="handleSubmit">{{ t('common.save') }}</el-button>
        <el-button @click="emit('cancel')">{{ t('common.cancel') }}</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.equipment-card {
  margin-bottom: 16px;
}

.equipment-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
}

.equipment-row .el-form-item {
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .system-config :deep(.el-form-item__label) {
    float: none;
    display: block;
    text-align: left;
    padding-bottom: 4px;
    width: 100% !important;
  }

  .system-config :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }

  .equipment-row {
    flex-direction: column;
    gap: 0;
  }

  .system-config :deep(.el-input-number) {
    width: 100% !important;
  }

  .system-config :deep(.el-row) {
    flex-direction: column;
  }

  .system-config :deep(.el-col) {
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>
