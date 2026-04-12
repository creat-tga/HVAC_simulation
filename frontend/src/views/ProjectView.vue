<script setup lang="ts">
import { onMounted, ref, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, VideoPlay } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useTaskTrackerStore } from '@/stores/taskTracker'
import { getProject } from '@/api/projects'
import { createBuilding, deleteBuilding } from '@/api/buildings'
import { getSimulations, runLoadSimulation } from '@/api/simulation'
import type { SimulationResult } from '@/types/simulation'
import type { Project } from '@/types/project'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getClimateZone } from '@/data/regions'
import { useResponsive } from '@/composables/useResponsive'

const { isMobile } = useResponsive()

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const tracker = useTaskTrackerStore()
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

// --- Batch Load Simulation ---
const runningBuildings = reactive<Set<string>>(new Set())

async function handleRunLoad(building: { id: string; name: string; zones?: unknown[] | null }) {
  if (!building.zones || building.zones.length === 0) {
    ElMessage.warning(t('building.noZonesWarning'))
    return
  }
  runningBuildings.add(building.id)
  try {
    const { data } = await runLoadSimulation(building.id)
    tracker.addTask({
      resultId: data.id,
      buildingId: building.id,
      buildingName: building.name,
      simulationType: 'load',
    })
    ElMessage.success(t('simulation.loadCalc.taskCreated'))
  } catch {
    ElMessage.error(t('simulation.loadCalc.failed'))
  } finally {
    runningBuildings.delete(building.id)
  }
}

async function handleRunAllLoads() {
  const buildings = store.buildings.filter(b => b.zones && b.zones.length > 0)
  if (buildings.length === 0) {
    ElMessage.warning(t('building.noZonesWarning'))
    return
  }
  for (const b of buildings) {
    await handleRunLoad(b)
  }
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
      <div>
        <el-button :icon="VideoPlay" @click="handleRunAllLoads" :disabled="store.buildings.length === 0">
          {{ t('building.runAllLoads') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="handleAddBuilding">
          {{ t('building.add') }}
        </el-button>
      </div>
    </div>

    <!-- Mobile: Card Layout -->
    <div v-if="isMobile" class="building-cards">
      <el-card
        v-for="row in store.buildings"
        :key="row.id"
        class="building-card"
        shadow="hover"
        @click="openBuilding(row.id)"
      >
        <div class="building-card-header">
          <span class="building-name">{{ row.name }}</span>
          <div class="building-tags">
            <el-tag v-if="row.building_type" size="small" type="info">
              {{ t(`building.types.${row.building_type}`) }}
            </el-tag>
            <el-tag v-if="row.climate_zone" size="small" type="warning">
              {{ t(`building.climateZones.${row.climate_zone}`) }}
            </el-tag>
          </div>
        </div>
        <div v-if="simMap[row.id]" class="building-card-sim">
          <div class="sim-item">
            <span class="sim-label">{{ t('building.peakCooling') }}</span>
            <span class="sim-value">{{ formatNum(simMap[row.id]?.peak_cooling_load) }}</span>
          </div>
          <div class="sim-item">
            <span class="sim-label">{{ t('building.peakHeating') }}</span>
            <span class="sim-value">{{ formatNum(simMap[row.id]?.peak_heating_load) }}</span>
          </div>
        </div>
        <div class="building-card-actions" @click.stop>
          <el-button
            size="small"
            :icon="VideoPlay"
            :loading="runningBuildings.has(row.id)"
            @click.stop="handleRunLoad(row)"
          >
            {{ t('building.runLoad') }}
          </el-button>
          <el-button
            type="danger"
            size="small"
            text
            :icon="Delete"
            @click.stop="handleDeleteBuilding(row.id)"
          >
            {{ t('common.delete') }}
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- Desktop: Table Layout -->
    <el-table v-else :data="store.buildings" v-loading="store.loading" stripe>
      <el-table-column prop="name" :label="t('building.name')" min-width="120" show-overflow-tooltip />
      <el-table-column :label="t('building.type')" width="120">
        <template #default="{ row }">
          {{ row.building_type ? t(`building.types.${row.building_type}`) : '-' }}
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
      <el-table-column :label="t('common.operation')" width="280" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            text
            :icon="VideoPlay"
            :loading="runningBuildings.has(row.id)"
            @click="handleRunLoad(row)"
          >
            {{ t('building.runLoad') }}
          </el-button>
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

@media (max-width: 768px) {
  .page-header h1 {
    font-size: 18px;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .section-header > div {
    display: flex;
    gap: 8px;
    width: 100%;
  }

  .section-header > div .el-button {
    flex: 1;
  }

  .section-header h2 {
    font-size: 16px;
  }

  .building-cards {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .building-card {
    cursor: pointer;
  }

  .building-card :deep(.el-card__body) {
    padding: 14px;
  }

  .building-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
  }

  .building-name {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
    flex: 1;
    margin-right: 8px;
  }

  .building-tags {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .building-card-sim {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    padding: 8px 0;
    border-top: 1px solid #f0f0f0;
  }

  .sim-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .sim-label {
    font-size: 12px;
    color: #94a3b8;
  }

  .sim-value {
    font-size: 14px;
    font-weight: 600;
    color: #334155;
  }

  .building-card-actions {
    display: flex;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px solid #f0f0f0;
  }
}
</style>
