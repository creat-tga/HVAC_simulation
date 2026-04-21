<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { TrendCharts, DataAnalysis } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const projectId = route.params.projectId as string

const cards = [
  {
    key: 'loads',
    icon: TrendCharts,
    color: '#0891b2',
    title: t('viz.loadsTitle'),
    desc: t('viz.loadsDesc'),
    path: `/projects/${projectId}/visualization/loads`,
  },
  {
    key: 'energy',
    icon: DataAnalysis,
    color: '#7c3aed',
    title: t('viz.energyTitle'),
    desc: t('viz.energyDesc'),
    path: `/projects/${projectId}/visualization/energy`,
  },
]
</script>

<template>
  <div class="ws-page">
    <div class="ws-page-header">
      <h2>{{ t('workspace.visualization') }}</h2>
      <p>{{ t('viz.entryHint') }}</p>
    </div>
    <div class="viz-cards">
      <div
        v-for="c in cards"
        :key="c.key"
        class="viz-card"
        :style="{ '--c': c.color } as any"
        @click="router.push(c.path)"
      >
        <el-icon :size="42"><component :is="c.icon" /></el-icon>
        <h3>{{ c.title }}</h3>
        <p>{{ c.desc }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ws-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}
.ws-page-header {
  margin-bottom: 24px;
}
.ws-page-header h2 {
  margin: 0 0 6px 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ws-page-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
.viz-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  max-width: 800px;
}
.viz-card {
  padding: 32px 24px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(226, 232, 240, 0.6);
  border-radius: 16px;
  cursor: pointer;
  text-align: center;
  transition: all 0.25s ease;
  color: var(--c);
}
.viz-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
  border-color: var(--c);
}
.viz-card h3 {
  margin: 14px 0 6px 0;
  font-size: 17px;
  color: #0f172a;
}
.viz-card p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
</style>
