<script setup lang="ts">
/**
 * Project workspace layout: left sidebar with 3 stages (建筑 / 系统 / 可视化).
 */
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'
import { getProject } from '@/api/projects'
import {
  OfficeBuilding,
  Setting,
  PieChart,
  ArrowLeft,
  Loading,
} from '@element-plus/icons-vue'
import TopActionBar from '@/components/layout/TopActionBar.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useProjectStore()

const projectId = computed(() => route.params.projectId as string)

interface NavItem {
  key: string
  label: string
  desc: string
  icon: any
  path: string
  matches: string[]
  step: number
  color: string
}

const navItems = computed<NavItem[]>(() => [
  {
    key: 'building',
    label: t('workspace.building'),
    desc: t('workspace.buildingHint'),
    icon: OfficeBuilding,
    path: `/projects/${projectId.value}/building`,
    matches: ['workspaceBuilding', 'building', 'loadCalc'],
    step: 1,
    color: '#0891b2',
  },
  {
    key: 'system',
    label: t('workspace.system'),
    desc: t('workspace.systemHint'),
    icon: Setting,
    path: `/projects/${projectId.value}/system`,
    matches: ['workspaceSystem', 'systemSelect', 'simulation'],
    step: 2,
    color: '#7c3aed',
  },
  {
    key: 'visualization',
    label: t('workspace.visualization'),
    desc: t('viz.entryHint'),
    icon: PieChart,
    path: `/projects/${projectId.value}/visualization`,
    matches: ['workspaceViz', 'workspaceVizLoads', 'workspaceVizEnergy', 'report'],
    step: 3,
    color: '#0d9488',
  },
])

function isActive(item: NavItem) {
  return item.matches.includes(route.name as string)
}

async function loadProject() {
  if (!projectId.value) return
  try {
    const { data } = await getProject(projectId.value)
    store.setCurrentProject(data)
    await store.fetchBuildings(projectId.value)
  } catch {
    /* axios interceptor handles errors */
  }
}

watch(projectId, loadProject, { immediate: false })
onMounted(loadProject)
</script>

<template>
  <div class="ws-layout">
    <aside class="ws-side">
      <button class="ws-back" @click="router.push('/projects')">
        <el-icon :size="14"><ArrowLeft /></el-icon>
        <span>{{ t('workspace.backToProjects') }}</span>
      </button>

      <div class="ws-proj-card">
        <div class="ws-proj-tag">{{ t('workspace.projectLabel') }}</div>
        <div class="ws-proj-name" :title="store.currentProject?.name">
          <el-icon v-if="!store.currentProject" :size="14" class="loading-ico"><Loading /></el-icon>
          {{ store.currentProject?.name || t('common.loading') }}
        </div>
        <div v-if="store.currentProject?.location" class="ws-proj-loc">
          📍 {{ store.currentProject.location }}
        </div>
      </div>

      <div class="ws-stage-label">{{ t('workspace.stages') }}</div>

      <nav class="ws-nav">
        <div
          v-for="item in navItems"
          :key="item.key"
          class="ws-item"
          :class="{ active: isActive(item) }"
          :style="{ '--c': item.color } as any"
          @click="router.push(item.path)"
        >
          <div class="ws-item-step">{{ item.step }}</div>
          <div class="ws-item-body">
            <div class="ws-item-title">
              <el-icon :size="14"><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </div>
            <div class="ws-item-desc">{{ item.desc }}</div>
          </div>
        </div>
      </nav>
    </aside>

    <main class="ws-main">
      <TopActionBar />
      <div class="ws-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.ws-layout {
  display: flex;
  height: 100vh;
  height: 100dvh;
  background: linear-gradient(135deg, #f8fafc 0%, #eef2f7 100%);
}

.ws-side {
  width: 264px;
  flex-shrink: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.85) 100%);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(226, 232, 240, 0.6);
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.ws-back {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  font-size: 12px;
  color: #64748b;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.18s;
  align-self: flex-start;
}
.ws-back:hover {
  color: #0891b2;
  background: rgba(6, 182, 212, 0.08);
}

.ws-proj-card {
  padding: 14px 14px 12px;
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.08), rgba(2, 132, 199, 0.04));
  border: 1px solid rgba(8, 145, 178, 0.18);
  border-radius: 12px;
}
.ws-proj-tag {
  font-size: 10px;
  letter-spacing: 0.1em;
  color: #0891b2;
  text-transform: uppercase;
  font-weight: 600;
  margin-bottom: 4px;
}
.ws-proj-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: -0.01em;
}
.loading-ico { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.ws-proj-loc {
  font-size: 11.5px;
  color: #64748b;
  margin-top: 6px;
}

.ws-stage-label {
  font-size: 10px;
  letter-spacing: 0.12em;
  color: #94a3b8;
  text-transform: uppercase;
  font-weight: 600;
  padding: 8px 8px 0;
}

.ws-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ws-item {
  display: flex;
  gap: 12px;
  padding: 12px 12px;
  border: 1px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  background: rgba(255, 255, 255, 0.5);
}
.ws-item:hover {
  background: color-mix(in srgb, var(--c) 7%, white);
  border-color: color-mix(in srgb, var(--c) 22%, transparent);
}
.ws-item.active {
  background: linear-gradient(135deg, color-mix(in srgb, var(--c) 14%, white), color-mix(in srgb, var(--c) 6%, white));
  border-color: color-mix(in srgb, var(--c) 32%, transparent);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--c) 14%, transparent);
}
.ws-item-step {
  width: 26px; height: 26px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--c) 12%, white);
  color: var(--c);
  font-size: 12px;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}
.ws-item.active .ws-item-step {
  background: var(--c);
  color: white;
}
.ws-item-body { flex: 1; min-width: 0; }
.ws-item-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 2px;
}
.ws-item.active .ws-item-title { color: var(--c); }
.ws-item-desc {
  font-size: 11.5px;
  color: #94a3b8;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.ws-main {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.ws-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  box-sizing: border-box;
}
.ws-content > * {
  min-width: 0;
}

@media (max-width: 768px) {
  .ws-layout { flex-direction: column; }
  .ws-side {
    width: 100%;
    flex-direction: row;
    padding: 8px 10px;
    gap: 8px;
    overflow-x: auto;
    overflow-y: hidden;
  }
  .ws-back, .ws-stage-label { display: none; }
  .ws-proj-card { flex-shrink: 0; padding: 8px 12px; }
  .ws-nav { flex-direction: row; }
  .ws-item { flex-shrink: 0; width: auto; padding: 8px 12px; }
  .ws-item-desc { display: none; }
}
</style>
