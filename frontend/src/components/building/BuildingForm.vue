<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BuildingCreate, EnvelopeParams } from '@/types/building'
import type { FormInstance, FormRules } from 'element-plus'

const { t } = useI18n()

const emit = defineEmits<{
  submit: [data: BuildingCreate]
  cancel: []
}>()

const formRef = ref<FormInstance>()

const form = reactive<BuildingCreate & { envelope_params: EnvelopeParams }>({
  name: '',
  building_type: '',
  total_area: undefined,
  floor_count: undefined,
  envelope_params: {
    wall_u_value: 1.0,
    window_u_value: 3.0,
    window_wall_ratio: 0.4,
    roof_u_value: 0.8,
    people_density: 0.1,
    lighting_density: 10,
    equipment_density: 15,
  },
})

const rules: FormRules = {
  name: [{ required: true, message: () => t('building.pleaseInputName'), trigger: 'blur' }],
  building_type: [{ required: true, message: () => t('building.pleaseSelectType'), trigger: 'change' }],
  total_area: [{ required: true, message: () => t('building.pleaseInputArea'), trigger: 'blur' }],
  floor_count: [{ required: true, message: () => t('building.pleaseInputFloors'), trigger: 'blur' }],
}

const buildingTypes = [
  'office', 'commercial', 'hotel', 'hospital',
  'school', 'residential', 'industrial', 'other',
]

const TEMPLATES: Record<string, { area: number; floors: number; envelope: EnvelopeParams }> = {
  office: {
    area: 10000, floors: 10,
    envelope: { wall_u_value: 0.8, window_u_value: 2.8, window_wall_ratio: 0.4, roof_u_value: 0.6, people_density: 0.1, lighting_density: 11, equipment_density: 15 },
  },
  commercial: {
    area: 20000, floors: 4,
    envelope: { wall_u_value: 0.7, window_u_value: 2.5, window_wall_ratio: 0.5, roof_u_value: 0.5, people_density: 0.15, lighting_density: 15, equipment_density: 10 },
  },
  hotel: {
    area: 15000, floors: 15,
    envelope: { wall_u_value: 0.8, window_u_value: 2.8, window_wall_ratio: 0.35, roof_u_value: 0.6, people_density: 0.05, lighting_density: 10, equipment_density: 8 },
  },
  hospital: {
    area: 25000, floors: 12,
    envelope: { wall_u_value: 0.6, window_u_value: 2.5, window_wall_ratio: 0.3, roof_u_value: 0.5, people_density: 0.08, lighting_density: 12, equipment_density: 20 },
  },
  school: {
    area: 8000, floors: 5,
    envelope: { wall_u_value: 1.0, window_u_value: 3.0, window_wall_ratio: 0.35, roof_u_value: 0.7, people_density: 0.3, lighting_density: 9, equipment_density: 5 },
  },
  residential: {
    area: 5000, floors: 18,
    envelope: { wall_u_value: 0.8, window_u_value: 2.8, window_wall_ratio: 0.3, roof_u_value: 0.6, people_density: 0.04, lighting_density: 6, equipment_density: 8 },
  },
}

function applyTemplate() {
  const tpl = TEMPLATES[form.building_type]
  if (tpl) {
    form.total_area = tpl.area
    form.floor_count = tpl.floors
    Object.assign(form.envelope_params, tpl.envelope)
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit('submit', { ...form })
}
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-width="auto" label-position="top">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-form-item :label="t('building.name')" prop="name">
          <el-input v-model="form.name" :placeholder="t('building.pleaseInputName')" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item :label="t('building.type')" prop="building_type">
          <el-select v-model="form.building_type" :placeholder="t('building.pleaseSelectType')" style="width: 100%">
            <el-option
              v-for="item in buildingTypes"
              :key="item"
              :label="t(`building.types.${item}`)"
              :value="item"
            />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>
    <el-form-item v-if="TEMPLATES[form.building_type]">
      <el-button type="success" size="small" @click="applyTemplate">
        {{ t('building.applyTemplate') }}
      </el-button>
      <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px">
        {{ t('building.templateHint') }}
      </span>
    </el-form-item>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-form-item :label="t('building.area')" prop="total_area">
          <el-input-number v-model="form.total_area" :min="1" :precision="1" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item :label="t('building.floors')" prop="floor_count">
          <el-input-number v-model="form.floor_count" :min="1" :max="200" style="width: 100%" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-divider>{{ t('building.envelope.title') }}</el-divider>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-form-item :label="t('building.envelope.wallU')">
          <el-input-number v-model="form.envelope_params.wall_u_value" :min="0.1" :max="5" :precision="2" :step="0.1" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item :label="t('building.envelope.windowU')">
          <el-input-number v-model="form.envelope_params.window_u_value" :min="0.5" :max="6" :precision="2" :step="0.1" style="width: 100%" />
        </el-form-item>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-form-item :label="t('building.envelope.wwr')">
          <el-input-number v-model="form.envelope_params.window_wall_ratio" :min="0.05" :max="0.9" :precision="2" :step="0.05" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item :label="t('building.envelope.roofU')">
          <el-input-number v-model="form.envelope_params.roof_u_value" :min="0.1" :max="3" :precision="2" :step="0.1" style="width: 100%" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-divider>{{ t('building.internalGains.title') }}</el-divider>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-form-item :label="t('building.internalGains.people')">
          <el-input-number v-model="form.envelope_params.people_density" :min="0" :max="1" :precision="3" :step="0.01" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item :label="t('building.internalGains.lighting')">
          <el-input-number v-model="form.envelope_params.lighting_density" :min="0" :max="50" :precision="1" :step="1" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item :label="t('building.internalGains.equipment')">
          <el-input-number v-model="form.envelope_params.equipment_density" :min="0" :max="50" :precision="1" :step="1" style="width: 100%" />
        </el-form-item>
      </el-col>
    </el-row>

    <el-form-item>
      <el-button type="primary" @click="handleSubmit">{{ t('common.save') }}</el-button>
      <el-button @click="emit('cancel')">{{ t('common.cancel') }}</el-button>
    </el-form-item>
  </el-form>
</template>
