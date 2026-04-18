<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSimulationDetail } from '@/api/simulation'
import { getEnergyReport, getCostReport, getCarbonReport } from '@/api/reports'
import type { SimulationDetail } from '@/types/simulation'
import type { EnergyReport, CostReport, CarbonReport } from '@/types/report'
import LoadChart from '@/components/charts/LoadChart.vue'
import EnergyChart from '@/components/charts/EnergyChart.vue'
import CostChart from '@/components/charts/CostChart.vue'

import { useResponsive } from '@/composables/useResponsive'

const { isMobile } = useResponsive()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const buildingId = route.params.buildingId as string
const resultId = route.params.resultId as string | undefined
const projectId = route.params.projectId as string

const activeTab = ref('energy')
const simulation = ref<SimulationDetail | null>(null)
const energyReport = ref<EnergyReport | null>(null)
const costReport = ref<CostReport | null>(null)
const carbonReport = ref<CarbonReport | null>(null)
const loading = ref(true)

function goToSimulation() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/simulation`)
}

onMounted(async () => {
  if (!resultId) {
    loading.value = false
    return
  }
  try {
    // Load simulation detail independently — it may fail for a new DB
    getSimulationDetail(buildingId, resultId)
      .then((res) => { simulation.value = res.data })
      .catch(() => { /* simulation detail not available */ })

    // Load report data — these always return data (with mock fallback)
    const [energyRes, costRes, carbonRes] = await Promise.all([
      getEnergyReport(resultId),
      getCostReport(resultId),
      getCarbonReport(resultId),
    ])
    energyReport.value = energyRes.data
    costReport.value = costRes.data
    carbonReport.value = carbonRes.data
  } catch (e) {
    console.error('Failed to load report data', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="report-view" v-loading="loading">
    <h1>{{ t('report.title') }}</h1>

    <!-- No result selected -->
    <template v-if="!resultId && !loading">
      <el-empty :description="t('report.noResult')">
        <el-button type="primary" @click="goToSimulation">{{ t('report.goToSimulation') }}</el-button>
      </el-empty>
    </template>

    <template v-else-if="energyReport || costReport || carbonReport">
      <!-- Summary Cards -->
      <el-row :gutter="20" class="summary-cards">
        <el-col :xs="12" :sm="6">
          <el-statistic :title="t('report.totalCooling')" :value="energyReport?.total_cooling_load ?? 0" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-statistic :title="t('report.totalHeating')" :value="energyReport?.total_heating_load ?? 0" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-statistic :title="t('report.totalEnergy')" :value="energyReport?.total_energy ?? 0" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-statistic :title="t('report.totalCarbon')" :value="carbonReport?.total_carbon ?? 0" />
        </el-col>
      </el-row>

      <!-- Charts Tabs -->
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('report.energyAnalysis')" name="energy">
          <template v-if="energyReport">
            <LoadChart
              :cooling-load="energyReport.hourly_cooling_load"
              :heating-load="energyReport.hourly_heating_load"
            />
            <el-divider />
            <EnergyChart
              :monthly-energy="energyReport.monthly_energy"
              :total-energy="energyReport.total_energy"
            />
          </template>
        </el-tab-pane>

        <el-tab-pane :label="t('report.costAnalysis')" name="cost">
          <template v-if="costReport">
            <el-descriptions :column="isMobile ? 1 : 3" border class="summary-desc">
              <el-descriptions-item :label="t('report.totalCost')">¥{{ costReport.total_cost.toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item :label="t('report.electricityCost')">¥{{ costReport.electricity_cost.toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item :label="t('report.gasCost')">{{ costReport.gas_cost != null ? `¥${costReport.gas_cost.toFixed(2)}` : '-' }}</el-descriptions-item>
            </el-descriptions>
            <CostChart
              :monthly-cost="costReport.monthly_cost"
              :total-cost="costReport.total_cost"
            />
          </template>
        </el-tab-pane>

        <el-tab-pane :label="t('report.carbonAnalysis')" name="carbon">
          <template v-if="carbonReport">
            <el-descriptions :column="isMobile ? 1 : 2" border class="summary-desc">
              <el-descriptions-item :label="t('report.totalCarbon')">{{ carbonReport.total_carbon.toFixed(1) }} kgCO₂</el-descriptions-item>
              <el-descriptions-item :label="t('report.carbonFactor')">{{ carbonReport.carbon_factor }} kgCO₂/kWh</el-descriptions-item>
            </el-descriptions>
          </template>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<style scoped>
h1 {
  margin: 0 0 24px;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.summary-cards {
  margin-bottom: 24px;
}

.summary-cards :deep(.el-statistic) {
  padding: 20px;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(226, 232, 240, 0.5);
  border-radius: 12px;
}

.summary-desc {
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  h1 {
    font-size: 18px;
    margin-bottom: 16px;
  }

  .summary-cards :deep(.el-statistic) {
    padding: 12px;
  }
}
</style>
