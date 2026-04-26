<script setup lang="ts">
/**
 * Project workspace layout: left sidebar with 3 stages (建筑 / 系统 / 可视化).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'
import { getProject } from '@/api/projects'
import {
  OfficeBuilding,
  Setting,
  PieChart,
  ArrowLeft,
  ArrowRight,
  Loading,
  Location,
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
    color: 'var(--brand-accent)',
  },
  {
    key: 'system',
    label: t('workspace.system'),
    desc: t('workspace.systemHint'),
    icon: Setting,
    path: `/projects/${projectId.value}/system-schemes`,
    matches: ['workspaceSystem', 'systemSchemeList', 'systemSchemeDetail', 'systemSelect', 'simulation'],
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

// G-2: sidebar collapse state with localStorage persistence
const SIDEBAR_KEY = 'hvac_workspace_sidebar_collapsed'
const sidebarCollapsed = ref<boolean>((() => {
  try { return localStorage.getItem(SIDEBAR_KEY) === '1' } catch { return false }
})())
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  try { localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed.value ? '1' : '0') } catch { /* ignore */ }
}
</script>

<template>
  <div class="ws-layout">
    <aside class="ws-side" :class="{ 'ws-side--collapsed': sidebarCollapsed }">
      <button v-if="!sidebarCollapsed" class="ws-back" @click="router.push('/projects')">
        <el-icon :size="14"><ArrowLeft /></el-icon>
        <span>{{ t('workspace.backToProjects') }}</span>
      </button>
      <button v-else class="ws-back ws-back--icon" @click="router.push('/projects')" :title="t('workspace.backToProjects')">
        <el-icon :size="16"><ArrowLeft /></el-icon>
      </button>

      <div v-if="!sidebarCollapsed" class="ws-proj-card">
        <div class="ws-proj-tag">{{ t('workspace.projectLabel') }}</div>
        <div class="ws-proj-name" :title="store.currentProject?.name">
          <el-icon v-if="!store.currentProject" :size="14" class="loading-ico"><Loading /></el-icon>
          {{ store.currentProject?.name || t('common.loading') }}
        </div>
        <div v-if="store.currentProject?.location" class="ws-proj-loc">
          <el-icon :size="12"><Location /></el-icon>
          {{ store.currentProject.location }}
        </div>
      </div>

      <div v-if="!sidebarCollapsed" class="ws-stage-label">{{ t('workspace.stages') }}</div>

      <nav class="ws-nav">
        <el-tooltip
          v-for="item in navItems"
          :key="item.key"
          :content="item.label"
          placement="right"
          :disabled="!sidebarCollapsed"
          :show-after="200"
        >
          <div
            class="ws-item"
            :class="{ active: isActive(item) }"
            :style="{ '--c': item.color } as any"
            @click="router.push(item.path)"
          >
            <div class="ws-item-step">{{ item.step }}</div>
            <div v-if="!sidebarCollapsed" class="ws-item-body">
              <div class="ws-item-title">
                <el-icon :size="14"><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </div>
              <div class="ws-item-desc">{{ item.desc }}</div>
            </div>
            <div v-else class="ws-item-mini-label">{{ item.label }}</div>
          </div>
        </el-tooltip>
      </nav>

      <button class="ws-collapse-btn" @click="toggleSidebar" :title="sidebarCollapsed ? '展开' : '折叠'">
        <el-icon :size="14"><component :is="sidebarCollapsed ? ArrowRight : ArrowLeft" /></el-icon>
      </button>
    </aside>

    <main class="ws-main">
      <TopActionBar />
      <!-- 视图自定义顶栏挂载点（Teleport 目标），位于 .ws-content 之外，不参与滚动 -->
      <div id="ws-mobile-topbar-slot"></div>
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
  background: linear-gradient(135deg, var(--color-neutral-50) 0%, var(--brand-primary-soft) 100%);
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
  overflow-x: hidden;
  transition: width var(--motion-normal) var(--easing-standard), padding var(--motion-normal) var(--easing-standard);
  position: relative;
}
.ws-side--collapsed {
  width: 64px;
  padding: 16px 8px;
}
.ws-collapse-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-pill);
  background: var(--surface-base);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  align-self: flex-end;
  margin-top: auto;
  box-shadow: var(--shadow-xs);
  transition: all var(--motion-fast) var(--easing-standard);
}
.ws-collapse-btn:hover {
  color: var(--brand-primary);
  border-color: var(--brand-primary);
  background: var(--brand-primary-soft);
}
.ws-side--collapsed .ws-collapse-btn {
  align-self: center;
}
.ws-back--icon {
  align-self: center;
  padding: 6px;
}
.ws-item-mini-label {
  font-size: 10px;
  color: var(--text-secondary);
  text-align: center;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 48px;
}
.ws-side--collapsed .ws-item {
  flex-direction: column;
  gap: 2px;
  align-items: center;
}
.ws-collapse-btn:hover {
  color: var(--brand-primary);
  border-color: var(--brand-primary);
}
.ws-side--collapsed .ws-nav { align-items: center; }
.ws-side--collapsed .ws-item {
  justify-content: center;
  padding: 8px;
}
.ws-side--collapsed .ws-item-step { margin: 0; }

.ws-back {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.18s;
  align-self: flex-start;
}
.ws-back:hover {
  color: var(--brand-accent);
  background: rgba(6, 182, 212, 0.08);
}

.ws-proj-card {
  padding: 14px 14px 12px;
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.08), rgba(2, 132, 199, 0.04));
  border: 1px solid rgba(8, 145, 178, 0.18);
  border-radius: var(--radius-lg);
}
.ws-proj-tag {
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--brand-accent);
  text-transform: uppercase;
  font-weight: var(--font-weight-semibold);
  margin-bottom: 4px;
}
.ws-proj-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: -0.01em;
}
.loading-ico { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.ws-proj-loc {
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-top: 6px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.ws-stage-label {
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
  font-weight: var(--font-weight-semibold);
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
  border-radius: var(--radius-lg);
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
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--c) 12%, white);
  color: var(--c);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
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
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
}
.ws-item.active .ws-item-title { color: var(--c); }
.ws-item-desc {
  font-size: 11.5px;
  color: var(--text-muted);
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
  /* 始终为竖向滚动条预留空间，避免内容增减时整页跳动。 */
  scrollbar-gutter: stable;
  display: flex;
  flex-direction: column;
  padding: 10px 16px;
  box-sizing: border-box;
}
.ws-content > * {
  min-width: 0;
}

@media (max-width: 768px) {
  .ws-content {
    padding: 10px 0;
    margin: 0;
  }
  .ws-layout { flex-direction: column; }

  /* 底部 tab bar 模式（仅阶段切换，返回按钮在 TopActionBar 左上角） */
  .ws-side, .ws-side--collapsed {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    width: 100%;
    height: auto;
    flex-direction: row;
    justify-content: space-around;
    align-items: stretch;
    padding: 6px 8px calc(6px + env(safe-area-inset-bottom, 0px));
    gap: 4px;
    overflow-x: hidden;
    overflow-y: hidden;
    border-top: 1px solid var(--border-subtle);
    border-right: none;
    background: var(--surface-base);
    box-shadow: 0 -2px 8px rgba(15, 23, 42, 0.06);
    z-index: 100;
    transition: none;
  }
  .ws-collapse-btn,
  .ws-stage-label,
  .ws-proj-card,
  .ws-back, .ws-back--icon { display: none; }
  .ws-nav {
    display: flex;
    flex: 1;
    flex-direction: row;
    justify-content: space-around;
    gap: 4px;
  }
  .ws-item {
    flex: 1;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 6px 4px;
    width: auto;
    text-align: center;
  }
  .ws-item-step { display: none; }
  .ws-item-body { display: flex; flex-direction: column; align-items: center; gap: 0; }
  .ws-item-title { font-size: 10px; gap: 2px; flex-direction: column; }
  .ws-item-title span { font-size: 10px; }
  .ws-item-desc { display: none; }

  /* main 预留 tab bar 高度 */
  .ws-main { padding-bottom: 56px; }
  .ws-content { padding-bottom: 8px; }
}
</style>
