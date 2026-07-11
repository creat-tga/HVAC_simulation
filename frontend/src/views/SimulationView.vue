<script setup lang="ts">
import { onMounted, ref, computed, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { VideoPlay } from '@element-plus/icons-vue'
import { useSimulationStore } from '@/stores/simulation'
import { useTaskTrackerStore } from '@/stores/taskTracker'
import { cancelSimulation, getSimulationStatus } from '@/api/simulation'
import { useSimulationWs } from '@/composables/useSimulationWs'
import SimulationProgress from '@/components/simulation/SimulationProgress.vue'
import StepNav from '@/components/layout/StepNav.vue'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useSimulationStore()
const tracker = useTaskTrackerStore()

const buildingId = route.params.buildingId as string
const projectId = route.params.projectId as string
const simRunning = ref(false)

// Active simulation tracking
const activeResultId = ref<string | null>(null)
const { status: wsStatus, progress: wsProgress, message: wsMessage, connected: wsConnected } =
  useSimulationWs(activeResultId)

// Polling fallback status
const pollStatus = ref<string>('pending')
const pollProgress = ref(0)
const pollMessage = ref('')

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!activeResultId.value) return
    try {
      const { data } = await getSimulationStatus(buildingId, activeResultId.value)
      pollStatus.value = data.status
      pollProgress.value = data.progress ?? 0
      pollMessage.value = data.error_message || ''
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        handleTaskComplete(data.status, data.error_message || undefined)
      }
    } catch {
      // ignore
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleTaskComplete(status: string, errorMessage?: string) {
  if (activeResultId.value) {
    tracker.updateTask(activeResultId.value, { status, progress: status === 'completed' ? 100 : undefined, errorMessage })
  }
  if (status === 'completed') {
    ElMessage.success(t('simulation.progress.completed'))
  } else if (status === 'failed') {
    ElMessage.error(errorMessage || t('simulation.runFailed'))
  } else if (status === 'cancelled') {
    ElMessage.warning(t('simulation.progress.cancelled'))
  }
  stopTracking()
  store.fetchEnergyResults(buildingId)
}

function stopTracking() {
  activeResultId.value = null
  simRunning.value = false
  stopPolling()
}

// Watch WebSocket terminal states
watch(
  () => wsStatus.value,
  (newStatus) => {
    if (['completed', 'failed', 'cancelled'].includes(newStatus) && activeResultId.value) {
      handleTaskComplete(newStatus, wsMessage.value || undefined)
    }
  },
)

// Check if load simulation is complete
const hasLoadResult = computed(() => store.latestLoadResult !== null)

onMounted(async () => {
  await Promise.all([
    store.fetchSystems(buildingId),
    store.fetchLoadResults(buildingId),
    store.fetchEnergyResults(buildingId),
  ])

  // Check for active (pending/running) energy simulation
  const active = store.energyResults.find(r => ['pending', 'running'].includes(r.status))
  if (active) {
    activeResultId.value = active.id
    simRunning.value = true
    // Immediate status check before starting polling
    try {
      const { data } = await getSimulationStatus(buildingId, active.id)
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        activeResultId.value = null
        simRunning.value = false
        await store.fetchEnergyResults(buildingId)
      } else {
        startPolling()
      }
    } catch {
      startPolling()
    }
  }
})

onUnmounted(() => {
  stopPolling()
})

async function handleRunSimulation() {
  ElMessage.info(t('simulation.useSchemeEnergy'))
  await router.push(`/projects/${projectId}/system-schemes`)
}

async function handleCancelSimulation() {
  if (!activeResultId.value) return
  try {
    await cancelSimulation(buildingId, activeResultId.value)
    ElMessage.warning(t('simulation.progress.cancelled'))
    stopTracking()
    store.fetchEnergyResults(buildingId)
  } catch {
    ElMessage.error(t('simulation.progress.cancelFailed'))
  }
}

function viewReport(resultId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/report/${resultId}`)
}

function goBack() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/system`)
}

function goToLoadCalc() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/load`)
}
</script>

<template>
  <div class="simulation-view">
    <div class="page-header">
      <h1>{{ t('nav.simulation') }}</h1>
    </div>

    <el-card>
      <div class="step-desc">
        <p>{{ t('simulation.energyStep.description') }}</p>
        <!-- Load result reference -->
        <div v-if="store.latestLoadResult" class="load-reference">
          <el-tag type="success" effect="plain">
            {{ t('simulation.loadPreview.peakCooling') }}: {{ store.latestLoadResult.peak_cooling_load?.toFixed(1) || '-' }} kW
          </el-tag>
          <el-tag type="warning" effect="plain">
            {{ t('simulation.loadPreview.peakHeating') }}: {{ store.latestLoadResult.peak_heating_load?.toFixed(1) || '-' }} kW
          </el-tag>
          <el-tag type="success" effect="plain">
            {{ t('system.title') }}: {{ store.systems.length }} {{ t('simulation.systemCount') }}
          </el-tag>
        </div>
      </div>

      <!-- No load result -->
      <div v-if="!hasLoadResult" class="hint-area">
        <el-empty :description="t('simulation.energyStep.noLoadResult')">
          <el-button type="primary" @click="goToLoadCalc">{{ t('simulation.energyStep.goToLoadCalc') }}</el-button>
        </el-empty>
      </div>

      <!-- No HVAC system -->
      <div v-else-if="!store.systemConfigured" class="hint-area">
        <el-empty :description="t('simulation.energyStep.hint')">
          <el-button type="primary" @click="goBack">{{ t('system.add') }}</el-button>
        </el-empty>
      </div>

      <template v-else>
        <!-- Progress Tracker -->
        <SimulationProgress
          v-if="activeResultId"
          :status="wsConnected ? wsStatus : pollStatus"
          :progress="wsConnected ? wsProgress : pollProgress"
          :message="wsConnected ? wsMessage : (pollMessage || t('simulation.progress.polling'))"
          :connected="wsConnected"
          @cancel="handleCancelSimulation"
        />

        <div v-else class="run-action">
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
        <div v-if="store.energyResults.length > 0" class="results-section">
          <h3>{{ t('simulation.results') }}</h3>
          <el-table :data="store.energyResults" stripe>
            <el-table-column :label="t('simulation.status')" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'cancelled' ? 'warning' : 'info'">
                  {{ t(`simulation.statusLabels.${row.status}`, row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('simulation.progress.label')" width="120">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.progress || 0"
                  :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
                  :stroke-width="6"
                />
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
    <StepNav
      :prev-label="t('nav.systemSelect')"
      @prev="goBack"
    />
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

@media (max-width: 768px) {
  .page-header h1 {
    font-size: 18px;
  }

  .load-reference {
    flex-direction: column;
  }

  .run-action {
    margin: 12px 0;
  }
}
</style>