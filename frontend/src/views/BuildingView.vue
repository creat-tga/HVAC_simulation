<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getBuilding, updateBuilding } from '@/api/buildings'
import type { Building, BuildingUpdate, EnvelopeParams } from '@/types/building'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const building = ref<Building | null>(null)
const editing = ref(false)
const editForm = ref<BuildingUpdate>({})
const editEnvelope = ref<EnvelopeParams>({})

const projectId = route.params.projectId as string
const buildingId = route.params.buildingId as string

onMounted(async () => {
  const { data } = await getBuilding(projectId, buildingId)
  building.value = data
})

function startEdit() {
  if (!building.value) return
  editForm.value = {
    name: building.value.name,
    building_type: building.value.building_type,
    total_area: building.value.total_area ?? undefined,
    floor_count: building.value.floor_count ?? undefined,
  }
  const ep = building.value.envelope_params || {}
  editEnvelope.value = {
    wall_u_value: ep.wall_u_value ?? 1.0,
    window_u_value: ep.window_u_value ?? 3.0,
    window_wall_ratio: ep.window_wall_ratio ?? 0.4,
    roof_u_value: ep.roof_u_value ?? 0.8,
    people_density: ep.people_density ?? 0.1,
    lighting_density: ep.lighting_density ?? 10,
    equipment_density: ep.equipment_density ?? 15,
  }
  editing.value = true
}

async function saveEdit() {
  editForm.value.envelope_params = editEnvelope.value
  const { data } = await updateBuilding(projectId, buildingId, editForm.value)
  building.value = data
  editing.value = false
  ElMessage.success(t('building.updateSuccess'))
}

function goSimulation() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/simulation`)
}

const buildingTypes = [
  'office', 'commercial', 'hotel', 'hospital',
  'school', 'residential', 'industrial', 'other',
]
</script>

<template>
  <div class="building-view" v-if="building">
    <div class="page-header">
      <h1>{{ building.name }}</h1>
      <div>
        <el-button @click="startEdit" v-if="!editing">{{ t('building.editInfo') }}</el-button>
        <el-button type="primary" @click="goSimulation">{{ t('building.enterSimulation') }}</el-button>
      </div>
    </div>

    <el-card v-if="!editing">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('building.name')">{{ building.name }}</el-descriptions-item>
        <el-descriptions-item :label="t('building.type')">{{ t(`building.types.${building.building_type}`) }}</el-descriptions-item>
        <el-descriptions-item :label="t('building.area')">{{ building.total_area ?? '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('building.floors')">{{ building.floor_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('building.climateZone')">
          {{ building.climate_zone ? t(`building.climateZones.${building.climate_zone}`) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('project.createdAt')">{{ new Date(building.created_at).toLocaleString() }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="building.envelope_params">
        <el-divider>{{ t('building.envelope.title') }}</el-divider>
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('building.envelope.wallU')">{{ building.envelope_params.wall_u_value ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('building.envelope.windowU')">{{ building.envelope_params.window_u_value ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('building.envelope.wwr')">{{ building.envelope_params.window_wall_ratio ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('building.envelope.roofU')">{{ building.envelope_params.roof_u_value ?? '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-divider>{{ t('building.internalGains.title') }}</el-divider>
        <el-descriptions :column="3" border>
          <el-descriptions-item :label="t('building.internalGains.people')">{{ building.envelope_params.people_density ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('building.internalGains.lighting')">{{ building.envelope_params.lighting_density ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('building.internalGains.equipment')">{{ building.envelope_params.equipment_density ?? '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-card>

    <el-card v-else>
      <el-form :model="editForm" label-width="160px">
        <el-form-item :label="t('building.name')">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item :label="t('building.type')">
          <el-select v-model="editForm.building_type">
            <el-option v-for="bt in buildingTypes" :key="bt" :label="t(`building.types.${bt}`)" :value="bt" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('building.area')">
          <el-input-number v-model="editForm.total_area" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item :label="t('building.floors')">
          <el-input-number v-model="editForm.floor_count" :min="1" :max="200" />
        </el-form-item>

        <el-divider>{{ t('building.envelope.title') }}</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('building.envelope.wallU')">
              <el-input-number v-model="editEnvelope.wall_u_value" :min="0.1" :max="5" :precision="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('building.envelope.windowU')">
              <el-input-number v-model="editEnvelope.window_u_value" :min="0.5" :max="6" :precision="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('building.envelope.wwr')">
              <el-input-number v-model="editEnvelope.window_wall_ratio" :min="0.05" :max="0.9" :precision="2" :step="0.05" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('building.envelope.roofU')">
              <el-input-number v-model="editEnvelope.roof_u_value" :min="0.1" :max="3" :precision="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>{{ t('building.internalGains.title') }}</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item :label="t('building.internalGains.people')">
              <el-input-number v-model="editEnvelope.people_density" :min="0" :max="1" :precision="3" :step="0.01" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('building.internalGains.lighting')">
              <el-input-number v-model="editEnvelope.lighting_density" :min="0" :max="50" :precision="1" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('building.internalGains.equipment')">
              <el-input-number v-model="editEnvelope.equipment_density" :min="0" :max="50" :precision="1" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" @click="saveEdit">{{ t('common.save') }}</el-button>
          <el-button @click="editing = false">{{ t('common.cancel') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}
</style>
