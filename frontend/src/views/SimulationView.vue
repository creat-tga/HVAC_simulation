<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { VideoPlay } from '@element-plus/icons-vue'
import { useSimulationStore } from '@/stores/simulation'
import { runSimulation } from '@/api/simulation'
import type { SimulationCreate } from '@/types/simulation'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useSimulationStore()

const buildingId = route.params.buildingId as string
const projectId = route.params.projectId as string
const simRunning = ref(false)

onMounted(() => {
  store.fetchSystems(buildingId)
  store.fetchResults(buildingId)
})

async function handleRunSimulation() {
  if (store.systems.length === 0) {
    ElMessage.warning(t('system.pleaseAddSystem'))
    return
  }
  simRunning.value = true
  try {
    const data: SimulationCreate = { simulation_type: 'full_year' }
    await runSimulation(buildingId, data)
    ElMessage.success(t('simulation.taskCreated'))
    store.fetchResults(buildingId)
  } catch {
    ElMessage.error(t('simulation.runFailed'))
  } finally {
    simRunning.value = false
  }
}

function viewReport(resultId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/report/${resultId}`)
}

function goBack() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/system`)
}
</script>

<template>
  <div class="simulation-view">
    <div class="page-header">
      <h1>{{ t('simulation.steps.energySimulation') }}</h1>
    </div>

    <el-card>
      <div class="step-desc">
        <p>{{ t('simulation.energyStep.description') }}</p>
        <div v-if="store.loadPreviewData" class="load-reference">
          <el-tag type="info" effect="plain">
            {{ t('simulation.loadPreview.peakCooling') }}: {{ store.loadPreviewData.peak_cooling_load.toFixed(1) }} kW
          </el-tag>
          <el-tag type="warning" effect="plain">
            {{ t('simulation.loadPreview.peakHeating') }}: {{ store.loadPreviewData.peak_heating_load.toFixed(1) }} kW
          </el-tag>
          <el-tag type="success" effect="plain">
            {{ t('system.title') }}: {{ store.systems.length }} {{ t('simulation.systemCount') }}
          </el-tag>
        </div>
      </div>

      <div v-if="!store.systemConfigured" class="hint-area">
        <el-empty :description="t('simulation.energyStep.hint')">
          <el-button type="primary" @click="goBack">{{ t('system.add') }}</el-button>
        </el-empty>
      </div>

      <template v-else>
        <div class="run-action">
          <el-button
            type="success"
            size="large"
            :icon="VideoPlay"
            :loading="simRunning"
            @click="handleRunSimulation"
          >
            {{ simRunning ? t('simulation.loadPreview.running') : t('simulation.run') }}
          </el-button>
        </div>

        <!-- Results Table -->
        <div v-if="store.results.length > 0" class="results-section">
          <h3>{{ t('simulation.results') }}</h3>
          <el-table :data="store.results" stripe>
            <el-table-column prop="simulation_type" :label="t('simulation.type')" width="120" />
            <el-table-column :label="t('simulation.status')" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
                  {{ t(`simulation.statusLabels.${row.status}`) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="total_energy" :label="t('simulation.totalEnergy')" width="140" />
            <el-table-column prop="total_cost" :label="t('simulation.totalCost')" width="140" />
            <el-table-column prop="total_carbon" :label="t('simulation.totalCarbon')" width="140" />
            <el-table-column :label="t('simulation.createdAt')">
              <template #default="{ row }">
                {{ new Date(row.created_at).toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column :label="t('common.operation')" width="100" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'completed'"
                  type="primary"
                  size="small"
                  text
                  @click="viewReport(row.id)"
                >
                  {{ t('simulation.viewReport') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-card>

    <!-- Navigation -->
    <div class="nav-buttons">
      <el-button @click="goBack">&larr; {{ t('simulation.steps.systemConfig') }}</el-button>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.step-desc {
  margin-bottom: 20px;
}

.step-desc p {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.load-reference {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.run-action {
  text-align: center;
  margin: 20px 0;
}

.hint-area {
  min-height: 150px;
}

.results-section {
  margin-top: 24px;
}

.results-section h3 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.nav-buttons {
  display: flex;
  justify-content: flex-start;
  margin-top: 24px;
}
</style>