<script setup lang="ts">
/**
 * Visualization > Loads. Pick a building to view its load simulation result.
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

const buildingResults = ref<Record<string, SimulationResult | null>>({})
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    if (store.buildings.length === 0) await store.fetchBuildings(projectId)
    for (const b of store.buildings) {
      try {
        const { data } = await getSimulations(b.id)
        const completed = data.filter(r => r.status === 'completed' && r.simulation_type === 'load')
        buildingResults.value[b.id] = completed[completed.length - 1] || null
      } catch {
        buildingResults.value[b.id] = null
      }
    }
  } finally {
    loading.value = false
  }
}

function viewReport(buildingId: string, resultId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/report/${resultId}`)
}

function gotoLoadCalc(buildingId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/load`)
}

onMounted(load)
</script>

<template>
  <div class="viz-page">
    <div class="viz-hero">
      <el-button text class="back-btn" @click="router.push(`/projects/${projectId}/visualization`)">
        ← {{ t('common.back') }}
      </el-button>
      <div class="hero-eyebrow">可视化 · 负荷结果</div>
      <h2>{{ t('viz.loadsTitle') }}</h2>
      <p class="hero-desc">选择一个建筑查看详细的冷热负荷仿真报告</p>
    </div>

    <el-empty v-if="!loading && store.buildings.length === 0" :description="t('workspace.noBuildings')" />

    <div v-else class="building-list" v-loading="loading">
      <div
        v-for="b in store.buildings"
        :key="b.id"
        class="b-row"
      >
        <div class="b-info">
          <div class="b-name">{{ b.name }}</div>
          <div class="b-meta">
            <el-tag v-if="buildingResults[b.id]" type="success" size="small">{{ t('viz.hasResult') }}</el-tag>
            <el-tag v-else type="info" size="small">{{ t('viz.noResult') }}</el-tag>
          </div>
        </div>
        <div class="b-actions">
          <el-button
            v-if="buildingResults[b.id]"
            type="primary"
            @click="viewReport(b.id, buildingResults[b.id]!.id)"
          >
            {{ t('viz.viewLoad') }}
          </el-button>
          <el-button v-else @click="gotoLoadCalc(b.id)">
            {{ t('viz.runLoadFirst') }}
          </el-button>
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
  background: linear-gradient(135deg, #ecfeff 0%, #ccfbf1 100%);
  border: 1px solid rgba(13, 148, 136, 0.16);
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
  color: #0d9488;
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
  gap: 12px;
}
.b-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.18s;
}
.b-row:hover {
  border-color: rgba(13, 148, 136, 0.4);
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.08);
}
.b-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}
.b-meta {
  margin-top: 6px;
  display: flex;
  gap: 6px;
}
</style>
