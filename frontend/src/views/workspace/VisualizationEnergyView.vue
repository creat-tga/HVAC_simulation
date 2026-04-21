<script setup lang="ts">
/**
 * Visualization > Energy. Pick a building/scheme to view its energy simulation result.
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'
import { getSimulations } from '@/api/simulation'
import type { SimulationResult } from '@/types/simulation'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useProjectStore()
const projectId = route.params.projectId as string

const buildingResults = ref<Record<string, SimulationResult[]>>({})
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    if (store.buildings.length === 0) await store.fetchBuildings(projectId)
    for (const b of store.buildings) {
      try {
        const { data } = await getSimulations(b.id)
        buildingResults.value[b.id] = data
          .filter(r => r.status === 'completed' && r.simulation_type !== 'load')
          .reverse()
      } catch {
        buildingResults.value[b.id] = []
      }
    }
  } finally {
    loading.value = false
  }
}

function viewReport(buildingId: string, resultId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/report/${resultId}`)
}

function gotoSimulation(buildingId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/simulation`)
}

onMounted(load)
</script>

<template>
  <div class="viz-page">
    <div class="viz-hero">
      <el-button text class="back-btn" @click="router.push(`/projects/${projectId}/visualization`)">
        ← {{ t('common.back') }}
      </el-button>
      <div class="hero-eyebrow">可视化 · 能耗结果</div>
      <h2>{{ t('viz.energyTitle') }}</h2>
      <p class="hero-desc">查看各建筑不同 HVAC 方案的能耗、费用与碳排放对比</p>
    </div>

    <el-empty v-if="!loading && store.buildings.length === 0" :description="t('workspace.noBuildings')" />

    <div v-else class="building-list" v-loading="loading">
      <div v-for="b in store.buildings" :key="b.id" class="b-card">
        <div class="b-card-header">
          <span class="b-name">{{ b.name }}</span>
          <el-button v-if="buildingResults[b.id]?.length === 0" size="small" @click="gotoSimulation(b.id)">
            {{ t('viz.runEnergyFirst') }}
          </el-button>
        </div>
        <div v-if="buildingResults[b.id]?.length" class="schemes">
          <div
            v-for="r in buildingResults[b.id]"
            :key="r.id"
            class="scheme"
            @click="viewReport(b.id, r.id)"
          >
            <div class="scheme-name">{{ r.simulation_type }}</div>
            <div class="scheme-meta">
              <span>{{ t('viz.totalEnergy') }}: <strong>{{ r.total_energy?.toFixed(0) || '-' }}</strong> kWh</span>
              <span>{{ t('viz.totalCost') }}: <strong>{{ r.total_cost?.toFixed(0) || '-' }}</strong> {{ t('common.yuan') }}</span>
              <span class="scheme-time">{{ new Date(r.created_at).toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.viz-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.viz-hero {
  position: relative;
  padding: 22px 26px 24px;
  border-radius: 16px;
  background: linear-gradient(135deg, #faf5ff 0%, #ede9fe 100%);
  border: 1px solid rgba(124, 58, 237, 0.16);
}
.back-btn {
  position: absolute;
  top: 14px;
  right: 18px;
}
.hero-eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7c3aed;
  margin-bottom: 6px;
}
.viz-hero h2 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.hero-desc {
  margin: 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.6;
}
.building-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.b-card {
  padding: 20px 22px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.18s;
}
.b-card:hover {
  border-color: rgba(124, 58, 237, 0.3);
}
.b-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.b-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}
.schemes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.scheme {
  padding: 14px 18px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.18s;
}
.scheme:hover {
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.06) 0%, rgba(124, 58, 237, 0.03) 100%);
  border-color: rgba(124, 58, 237, 0.3);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.08);
}
.scheme-name {
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
  font-size: 14px;
}
.scheme-meta {
  display: flex;
  gap: 18px;
  font-size: 12px;
  color: #64748b;
  flex-wrap: wrap;
}
.scheme-meta strong {
  color: #0f172a;
  font-weight: 700;
}
.scheme-time {
  margin-left: auto;
  color: #94a3b8;
}
</style>
