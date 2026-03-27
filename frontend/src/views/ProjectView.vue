<script setup lang="ts">
import { onMounted, ref, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { getProject } from '@/api/projects'
import { createBuilding, deleteBuilding } from '@/api/buildings'
import { getSimulations } from '@/api/simulation'
import type { SimulationResult } from '@/types/simulation'
import type { Project } from '@/types/project'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getClimateZone } from '@/data/regions'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const { t } = useI18n()

const project = ref<Project | null>(null)
const projectId = route.params.projectId as string

// Simulation results per building
const simMap = reactive<Record<string, SimulationResult | null>>({})

async function fetchSimResults() {
  for (const b of store.buildings) {
    try {
      const { data } = await getSimulations(b.id)
      const completed = data.filter(r => r.status === 'completed')
      simMap[b.id] = completed.length > 0 ? completed[completed.length - 1] : null
    } catch {
      simMap[b.id] = null
    }
  }
}

function formatNum(val: number | null | undefined) {
  if (val == null) return '-'
  return val >= 1000 ? val.toFixed(0) : val.toFixed(1)
}

// Description overflow detection
const descRef = ref<HTMLElement>()
const descOverflow = ref(false)

function checkDescOverflow() {
  if (descRef.value) {
    descOverflow.value = descRef.value.scrollHeight > descRef.value.clientHeight + 1
  }
}

watch(() => store.buildings, () => {
  if (store.buildings.length > 0) fetchSimResults()
})

onMounted(async () => {
  const { data } = await getProject(projectId)
  project.value = data
  store.setCurrentProject(data)
  await store.fetchBuildings(projectId)
})

async function handleAddBuilding() {
  const climate_zone = project.value?.location
    ? getClimateZone(project.value.location.split('-')[0])
    : undefined
  const { data } = await createBuilding(projectId, {
    name: t('building.defaultName'),
    building_type: 'office',
    climate_zone,
  })
  ElMessage.success(t('building.createSuccess'))
  await store.fetchBuildings(projectId)
  router.push(`/projects/${projectId}/buildings/${data.id}`)
}

async function handleDeleteBuilding(buildingId: string) {
  await ElMessageBox.confirm(t('building.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteBuilding(projectId, buildingId)
  ElMessage.success(t('building.deleteSuccess'))
  delete simMap[buildingId]
  await store.fetchBuildings(projectId)
}

function openBuilding(buildingId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}`)
}
</script>

<template>
  <div class="project-view">
    <div class="page-header">
      <div>
        <h1>{{ project?.name }}</h1>
        <el-tooltip
          :content="project?.description || ''"
          placement="bottom"
          :disabled="!descOverflow"
          effect="light"
          :show-after="300"
          :popper-style="{ maxWidth: '1200px', lineHeight: '1.6', padding: '12px 16px' }"
        >
          <p ref="descRef" class="description" @mouseenter="checkDescOverflow">{{ project?.description || t('project.noDescription') }}</p>
        </el-tooltip>
        <el-tag v-if="project?.location" type="info" style="margin-top: 8px">
          📍 {{ project.location }}
        </el-tag>
      </div>
    </div>

    <el-divider />

    <div class="section-header">
      <h2>{{ t('building.title') }}</h2>
      <el-button type="primary" :icon="Plus" @click="handleAddBuilding">
        {{ t('building.add') }}
      </el-button>
    </div>

    <el-table :data="store.buildings" v-loading="store.loading" stripe>
      <el-table-column prop="name" :label="t('building.name')" min-width="120" show-overflow-tooltip />
      <el-table-column :label="t('building.type')" width="120">
        <template #default="{ row }">
          {{ t(`building.types.${row.building_type}`) }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.climateZone')" width="120">
        <template #default="{ row }">
          {{ row.climate_zone ? t(`building.climateZones.${row.climate_zone}`) : '-' }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.peakCooling')" width="120" align="right">
        <template #default="{ row }">
          {{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_cooling_load) : t('building.noSimulation') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.peakHeating')" width="120" align="right">
        <template #default="{ row }">
          {{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_heating_load) : t('building.noSimulation') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.totalCooling')" width="130" align="right">
        <template #default="{ row }">
          {{ simMap[row.id] ? formatNum(simMap[row.id]?.total_cooling_load) : t('building.noSimulation') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.totalHeating')" width="130" align="right">
        <template #default="{ row }">
          {{ simMap[row.id] ? formatNum(simMap[row.id]?.total_heating_load) : t('building.noSimulation') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.totalEnergy')" width="130" align="right">
        <template #default="{ row }">
          {{ simMap[row.id] ? formatNum(simMap[row.id]?.total_energy) : t('building.noSimulation') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('building.totalCost')" width="130" align="right">
        <template #default="{ row }">
          {{ simMap[row.id] ? formatNum(simMap[row.id]?.total_cost) : t('building.noSimulation') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('common.operation')" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" text @click="openBuilding(row.id)">
            {{ t('building.config') }}
          </el-button>
          <el-button
            type="danger"
            size="small"
            text
            :icon="Delete"
            @click="handleDeleteBuilding(row.id)"
          >
            {{ t('common.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!store.loading && store.buildings.length === 0" :description="t('building.noBuildings')" />
  </div>
</template>

<style scoped>
.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.description {
  color: #64748b;
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  max-height: 45px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}
</style>
