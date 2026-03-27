<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { VideoPlay, Loading } from '@element-plus/icons-vue'
import { useSimulationStore } from '@/stores/simulation'
import { previewLoad } from '@/api/simulation'
import LoadChart from '@/components/charts/LoadChart.vue'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useSimulationStore()

const buildingId = route.params.buildingId as string
const projectId = route.params.projectId as string
const loadRunning = ref(false)

async function handleRunLoadPreview() {
  loadRunning.value = true
  try {
    const { data } = await previewLoad(buildingId)
    store.setLoadPreview(data)
    ElMessage.success(t('simulation.loadPreview.completed'))
  } catch {
    ElMessage.error(t('simulation.loadPreview.failed'))
  } finally {
    loadRunning.value = false
  }
}

function goToSystemSelect() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/system`)
}

function goBack() {
  router.push(`/projects/${projectId}/buildings/${buildingId}`)
}
</script>

<template>
  <div class="load-calc-view">
    <div class="page-header">
      <h1>{{ t('simulation.loadPreview.title') }}</h1>
    </div>

    <el-card>
      <div class="step-desc">
        <p>{{ t('simulation.loadPreview.description') }}</p>
      </div>

      <div class="load-action">
        <el-button
          type="primary"
          size="large"
          :icon="loadRunning ? Loading : VideoPlay"
          :loading="loadRunning"
          @click="handleRunLoadPreview"
        >
          {{ loadRunning ? t('simulation.loadPreview.running') : t('simulation.loadPreview.runLoad') }}
        </el-button>
      </div>

      <template v-if="store.loadPreviewData">
        <!-- Load Summary Cards -->
        <el-row :gutter="16" class="load-summary">
          <el-col :span="6">
            <div class="summary-card summary-cooling">
              <div class="summary-label">{{ t('simulation.loadPreview.totalCooling') }}</div>
              <div class="summary-value">{{ (store.loadPreviewData.total_cooling_load / 1000).toFixed(1) }} <span>MWh</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-heating">
              <div class="summary-label">{{ t('simulation.loadPreview.totalHeating') }}</div>
              <div class="summary-value">{{ (store.loadPreviewData.total_heating_load / 1000).toFixed(1) }} <span>MWh</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-peak-cool">
              <div class="summary-label">{{ t('simulation.loadPreview.peakCooling') }}</div>
              <div class="summary-value">{{ store.loadPreviewData.peak_cooling_load.toFixed(1) }} <span>kW</span></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card summary-peak-heat">
              <div class="summary-label">{{ t('simulation.loadPreview.peakHeating') }}</div>
              <div class="summary-value">{{ store.loadPreviewData.peak_heating_load.toFixed(1) }} <span>kW</span></div>
            </div>
          </el-col>
        </el-row>

        <!-- Load Chart -->
        <LoadChart
          :cooling-load="store.loadPreviewData.hourly_cooling_load"
          :heating-load="store.loadPreviewData.hourly_heating_load"
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

.step-desc {
  margin-bottom: 20px;
}

.step-desc p {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.load-action {
  text-align: center;
  margin: 20px 0;
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
