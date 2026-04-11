<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSimulationStore } from '@/stores/simulation'
import { useTaskTrackerStore } from '@/stores/taskTracker'
import { getSimulationStatus, getSimulationDetail, getWeatherData } from '@/api/simulation'
import { useSimulationWs } from '@/composables/useSimulationWs'
import SimulationProgress from '@/components/simulation/SimulationProgress.vue'
import LoadChart from '@/components/charts/LoadChart.vue'
import WeatherChart from '@/components/charts/WeatherChart.vue'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useSimulationStore()
const tracker = useTaskTrackerStore()

const buildingId = route.params.buildingId as string
const projectId = route.params.projectId as string

// Weather data
const weatherData = ref<{
  dry_bulb_temperature: number[]
  dew_point_temperature: number[]
  relative_humidity: number[]
  location: { name: string; lat: number; lon: number; elev: number }
} | null>(null)
const weatherLoading = ref(false)
const weatherError = ref('')

// Active task tracking
const activeResultId = ref<string | null>(null)
const { status: wsStatus, progress: wsProgress, message: wsMessage, connected: wsConnected } =
  useSimulationWs(activeResultId)

// Completed load result data (for display)
const completedLoadData = ref<{
  hourly_cooling_load: number[]
  hourly_heating_load: number[]
  total_cooling_load: number
  total_heating_load: number
  peak_cooling_load: number
  peak_heating_load: number
} | null>(null)

// Polling fallback status
const pollStatus = ref<string>('pending')
const pollProgress = ref(0)
const pollMessage = ref('')

// Polling fallback
let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!activeResultId.value) return
    try {
      const { data } = await getSimulationStatus(buildingId, activeResultId.value)
      // Always update polling state for progress display
      pollStatus.value = data.status
      pollProgress.value = data.progress ?? 0
      pollMessage.value = data.error_message || ''
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        await handleTaskComplete(data.status, data.error_message || undefined)
      }
    } catch {
      // ignore poll errors
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleTaskComplete(status: string, errorMessage?: string) {
  if (activeResultId.value) {
    tracker.updateTask(activeResultId.value, { status, progress: status === 'completed' ? 100 : undefined, errorMessage })
  }
  if (status === 'completed' && activeResultId.value) {
    ElMessage.success(t('simulation.loadCalc.completed'))
    // Fetch the completed result to get hourly data
    try {
      const { data } = await getSimulationDetail(buildingId, activeResultId.value)
      if (data.hourly_cooling_load && data.hourly_heating_load) {
        completedLoadData.value = {
          hourly_cooling_load: data.hourly_cooling_load,
          hourly_heating_load: data.hourly_heating_load,
          total_cooling_load: data.total_cooling_load || 0,
          total_heating_load: data.total_heating_load || 0,
          peak_cooling_load: data.peak_cooling_load || 0,
          peak_heating_load: data.peak_heating_load || 0,
        }
        // Also set as load preview for downstream use
        store.setLoadPreview(completedLoadData.value)
      }
    } catch {
      // ignore
    }
  } else if (status === 'failed') {
    ElMessage.error(errorMessage || t('simulation.loadCalc.failed'))
  } else if (status === 'cancelled') {
    ElMessage.warning(t('simulation.progress.cancelled'))
  }
  stopTracking()
  store.fetchLoadResults(buildingId)
}

function stopTracking() {
  activeResultId.value = null
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

function goToSystemSelect() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/system`)
}

function goBack() {
  router.push(`/projects/${projectId}/buildings/${buildingId}`)
}

// Load existing results on mount
onMounted(async () => {
  await store.fetchLoadResults(buildingId)
  // Check for active (pending/running) load simulation
  const active = store.loadResults.find(r => ['pending', 'running'].includes(r.status))
  if (active) {
    activeResultId.value = active.id
    // Immediate status check before starting polling
    try {
      const { data } = await getSimulationStatus(buildingId, active.id)
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        // Task already finished, don't poll
        activeResultId.value = null
        await store.fetchLoadResults(buildingId)
      } else {
        startPolling()
      }
    } catch {
      // If status check fails, still try polling
      startPolling()
    }
  }
  // Load latest completed result
  const latest = store.latestLoadResult
  if (latest) {
    try {
      const { data } = await getSimulationDetail(buildingId, latest.id)
      if (data.hourly_cooling_load && data.hourly_heating_load) {
        completedLoadData.value = {
          hourly_cooling_load: data.hourly_cooling_load,
          hourly_heating_load: data.hourly_heating_load,
          total_cooling_load: data.total_cooling_load || 0,
          total_heating_load: data.total_heating_load || 0,
          peak_cooling_load: data.peak_cooling_load || 0,
          peak_heating_load: data.peak_heating_load || 0,
        }
        store.setLoadPreview(completedLoadData.value)
      }
    } catch {
      // ignore
    }
  }

  // Fetch weather data
  weatherLoading.value = true
  try {
    const { data: wd } = await getWeatherData(buildingId)
    weatherData.value = wd
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    weatherError.value = detail || t('weather.loadFailed')
  } finally {
    weatherLoading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})

// Display data: either from completed task or previous results
const displayData = computed(() => completedLoadData.value)
</script>

<template>
  <div class="load-calc-view">
    <div class="page-header">
      <h1>{{ t('weather.pageTitle') }}</h1>
    </div>

    <!-- Weather Data Section -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>{{ t('weather.title') }}</span>
        </div>
      </template>

      <div v-if="weatherLoading" v-loading="true" style="height: 200px" />
      <div v-else-if="weatherError" class="weather-error">
        <el-empty :description="weatherError" />
      </div>
      <template v-else-if="weatherData">
        <!-- Weather Summary -->
        <el-row :gutter="16" class="load-summary">
          <el-col :span="6">
            <div class="summary-card summary-cooling">
              <div class="summary-label">{{ t('weather.maxDryBulb') }}</div>
              <div class="summary-value">{{ Math.max(...weatherData.dry_bulb_temperature).toFixed(1) }} <span>°C</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-heating">
              <div class="summary-label">{{ t('weather.minDryBulb') }}</div>
              <div class="summary-value">{{ Math.min(...weatherData.dry_bulb_temperature).toFixed(1) }} <span>°C</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-peak-cool">
              <div class="summary-label">{{ t('weather.avgDryBulb') }}</div>
              <div class="summary-value">{{ (weatherData.dry_bulb_temperature.reduce((a, b) => a + b, 0) / weatherData.dry_bulb_temperature.length).toFixed(1) }} <span>°C</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-peak-heat">
              <div class="summary-label">{{ t('weather.avgHumidity') }}</div>
              <div class="summary-value">{{ (weatherData.relative_humidity.reduce((a, b) => a + b, 0) / weatherData.relative_humidity.length).toFixed(0) }} <span>%</span></div>
            </div>
          </el-col>
        </el-row>

        <WeatherChart
          :dry-bulb-temperature="weatherData.dry_bulb_temperature"
          :dew-point-temperature="weatherData.dew_point_temperature"
          :relative-humidity="weatherData.relative_humidity"
        />
      </template>
    </el-card>

    <!-- Load Results Section -->
    <el-card class="section-card">
      <template #header>
        <span>{{ t('weather.loadResults') }}</span>
      </template>

      <!-- Progress Tracker (for tasks started from Project overview) -->
      <SimulationProgress
        v-if="activeResultId"
        :status="wsConnected ? wsStatus : pollStatus"
        :progress="wsConnected ? wsProgress : pollProgress"
        :message="wsConnected ? wsMessage : (pollMessage || t('simulation.progress.polling'))"
        :connected="wsConnected"
      />

      <!-- No data hint -->
      <el-empty
        v-else-if="!displayData"
        :description="t('simulation.loadCalc.noDataHint')"
      />

      <template v-if="displayData">
        <!-- Load Summary Cards -->
        <el-row :gutter="16" class="load-summary">
          <el-col :span="6">
            <div class="summary-card summary-cooling">
              <div class="summary-label">{{ t('simulation.loadPreview.totalCooling') }}</div>
              <div class="summary-value">{{ (displayData.total_cooling_load / 1000).toFixed(1) }} <span>MWh</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-heating">
              <div class="summary-label">{{ t('simulation.loadPreview.totalHeating') }}</div>
              <div class="summary-value">{{ (displayData.total_heating_load / 1000).toFixed(1) }} <span>MWh</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-peak-cool">
              <div class="summary-label">{{ t('simulation.loadPreview.peakCooling') }}</div>
              <div class="summary-value">{{ displayData.peak_cooling_load.toFixed(1) }} <span>kW</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-peak-heat">
              <div class="summary-label">{{ t('simulation.loadPreview.peakHeating') }}</div>
              <div class="summary-value">{{ displayData.peak_heating_load.toFixed(1) }} <span>kW</span></div>
            </div>
          </el-col>
        </el-row>

        <!-- Load Chart -->
        <LoadChart
          :cooling-load="displayData.hourly_cooling_load"
          :heating-load="displayData.hourly_heating_load"
        />
      </template>
    </el-card>

    <!-- Navigation -->
    <div class="nav-buttons">
      <el-button @click="goBack">← {{ t('nav.buildingConfig') }}</el-button>
      <el-button
        type="primary"
        :disabled="!store.loadCompleted"
        @click="goToSystemSelect"
      >
        {{ t('simulation.loadPreview.nextStep') }} →
      </el-button>
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

.section-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.load-summary {
  margin: 20px 0;
}

.summary-card {
  padding: 16px;
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.5);
  text-align: center;
}

.summary-card .summary-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
  font-weight: 500;
}

.summary-card .summary-value {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.summary-card .summary-value span {
  font-size: 13px;
  font-weight: 400;
  color: #94a3b8;
}

.summary-cooling {
  background: rgba(6, 182, 212, 0.06);
  border-color: rgba(6, 182, 212, 0.2);
}

.summary-heating {
  background: rgba(251, 146, 60, 0.06);
  border-color: rgba(251, 146, 60, 0.2);
}

.summary-peak-cool {
  background: rgba(59, 130, 246, 0.06);
  border-color: rgba(59, 130, 246, 0.2);
}

.summary-peak-heat {
  background: rgba(239, 68, 68, 0.06);
  border-color: rgba(239, 68, 68, 0.2);
}

.nav-buttons {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
}
</style>
