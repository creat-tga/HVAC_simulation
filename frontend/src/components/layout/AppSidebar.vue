<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'
import { useSimulationStore } from '@/stores/simulation'
import {
  HomeFilled,
  OfficeBuilding,
  ArrowDown,
  Check,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useProjectStore()
const simStore = useSimulationStore()

const projectId = computed(() => route.params.projectId as string | undefined)
const buildingId = computed(() => route.params.buildingId as string | undefined)

// Ensure buildings are loaded when navigating directly to a building page
watch(
  projectId,
  (pid) => {
    if (pid && store.buildings.length === 0) {
      store.fetchBuildings(pid)
    }
  },
  { immediate: true },
)

const currentBuilding = computed(() =>
  store.buildings.find(b => b.id === buildingId.value),
)

// Workflow steps definition
const workflowSteps = computed(() => {
  if (!projectId.value || !buildingId.value) return []
  const base = `/projects/${projectId.value}/buildings/${buildingId.value}`
  return [
    {
      step: 1,
      name: 'building',
      label: t('nav.buildingConfig'),
      desc: t('nav.stepDesc.building'),
      path: base,
      icon: '📐',
      completed: !!(currentBuilding.value && currentBuilding.value.zones && currentBuilding.value.zones.length > 0),
    },
    {
      step: 2,
      name: 'loadCalc',
      label: t('nav.loadWeather'),
      desc: t('nav.stepDesc.load'),
      path: `${base}/load`,
      icon: '📊',
      completed: simStore.loadCompleted,
    },
    {
      step: 3,
      name: 'systemSelect',
      label: t('nav.systemSelect'),
      desc: t('nav.stepDesc.system'),
      path: `${base}/system`,
      icon: '⚙️',
      completed: simStore.systemConfigured,
    },
    {
      step: 4,
      name: 'simulation',
      label: t('nav.simulation'),
      desc: t('nav.stepDesc.energy'),
      path: `${base}/simulation`,
      icon: '🔬',
      completed: simStore.energyResults.some(r => r.status === 'completed'),
    },
    {
      step: 5,
      name: 'report',
      label: t('nav.report'),
      desc: t('nav.stepDesc.report'),
      path: `${base}/report`,
      icon: '📈',
      completed: false,
    },
  ]
})

// Current active step
const currentStep = computed(() => {
  const step = route.meta.step as number | undefined
  return step || 0
})

function isActive(name: string) {
  return route.name === name
}

function navigate(path: string) {
  router.push(path)
}

function switchBuilding(bid: string) {
  // Navigate to same sub-page for the new building
  const routeName = route.name as string
  const base = `/projects/${projectId.value}/buildings/${bid}`
  if (routeName === 'loadCalc') router.push(`${base}/load`)
  else if (routeName === 'systemSelect') router.push(`${base}/system`)
  else if (routeName === 'simulation') router.push(`${base}/simulation`)
  else if (routeName === 'report') router.push(`${base}/report`)
  else router.push(base)
}
</script>

<template>
  <el-aside width="240px" class="app-sidebar">
    <nav class="sidebar-nav">
      <!-- Group 1: Project Management -->
      <div class="nav-group">
        <div class="nav-group-title">{{ t('nav.groupProject') }}</div>
        <div
          class="nav-item"
          :class="{ 'is-active': route.name === 'home' }"
          @click="navigate('/')"
        >
          <el-icon :size="16"><HomeFilled /></el-icon>
          <span>{{ t('nav.projectList') }}</span>
        </div>
        <div
          v-if="projectId"
          class="nav-item"
          :class="{ 'is-active': route.name === 'project' }"
          @click="navigate(`/projects/${projectId}`)"
        >
          <el-icon :size="16"><OfficeBuilding /></el-icon>
          <span>{{ t('nav.projectOverview') }}</span>
        </div>
      </div>

      <!-- Group 2: Simulation Workflow (only when in building context) -->
      <template v-if="projectId && buildingId">
        <div class="nav-group">
          <div class="nav-group-title">{{ t('nav.groupBuilding') }}</div>

          <!-- Building Switcher -->
          <el-dropdown
            v-if="store.buildings.length > 1"
            trigger="click"
            @command="switchBuilding"
            :teleported="false"
            class="building-switcher"
          >
            <div class="building-switcher-trigger">
              <span class="building-name">{{ currentBuilding?.name || '—' }}</span>
              <el-icon :size="12"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="b in store.buildings"
                  :key="b.id"
                  :command="b.id"
                  :class="{ 'is-current': b.id === buildingId }"
                >
                  {{ b.name }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <div
            v-else
            class="building-switcher-trigger static"
          >
            <span class="building-name">{{ currentBuilding?.name || '—' }}</span>
          </div>

          <!-- Workflow Steps -->
          <div class="workflow-steps">
            <div
              v-for="ws in workflowSteps"
              :key="ws.step"
              class="workflow-step"
              :class="{
                'is-active': isActive(ws.name),
                'is-completed': ws.completed && !isActive(ws.name),
                'is-future': ws.step > currentStep && !ws.completed,
              }"
              @click="navigate(ws.path)"
            >
              <div class="step-indicator">
                <div class="step-line-top" v-if="ws.step > 1" />
                <div class="step-circle">
                  <el-icon v-if="ws.completed && !isActive(ws.name)" :size="12"><Check /></el-icon>
                  <span v-else>{{ ws.step }}</span>
                </div>
                <div class="step-line-bottom" v-if="ws.step < 5" />
              </div>
              <div class="step-content">
                <div class="step-label">{{ ws.label }}</div>
                <div class="step-desc">{{ ws.desc }}</div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </nav>
  </el-aside>
</template>

<style scoped>
.app-sidebar {
  border-right: 1px solid rgba(226, 232, 240, 0.4);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.65) 0%, rgba(248, 250, 252, 0.55) 100%);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-nav {
  padding: 20px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* ── Nav Groups ── */
.nav-group {
  margin-bottom: 8px;
}

.nav-group + .nav-group {
  padding-top: 8px;
  border-top: 1px solid rgba(226, 232, 240, 0.35);
}

.nav-group-title {
  font-size: 10.5px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 4px 14px 6px;
  margin-bottom: 2px;
  user-select: none;
}

/* ── Nav Items ── */
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 500;
  color: #64748b;
  transition: all 0.18s ease;
  user-select: none;
  position: relative;
}

.nav-item:hover {
  background: rgba(6, 182, 212, 0.06);
  color: #0e7490;
}

.nav-item:active {
  transform: scale(0.98);
}

.nav-item.is-active {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.13), rgba(2, 132, 199, 0.07));
  color: #0891b2;
  font-weight: 600;
  box-shadow: inset 3px 0 0 #0891b2;
}

.nav-item.is-active .el-icon {
  color: #0891b2;
}

/* ── Workflow Steps ── */
.workflow-steps {
  padding: 4px 0 0 6px;
}

.workflow-step {
  display: flex;
  gap: 10px;
  cursor: pointer;
  transition: all 0.18s ease;
  user-select: none;
  padding-right: 8px;
}

.workflow-step:hover .step-content {
  background: rgba(6, 182, 212, 0.05);
}

.workflow-step:active {
  transform: scale(0.98);
}

/* Step indicator (circle + lines) */
.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}

.step-line-top,
.step-line-bottom {
  width: 2px;
  flex: 1;
  background: rgba(203, 213, 225, 0.5);
  transition: background 0.2s;
}

.workflow-step.is-completed .step-line-top,
.workflow-step.is-completed .step-line-bottom {
  background: #06b6d4;
}

.workflow-step.is-active .step-line-top {
  background: #06b6d4;
}

.step-circle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.12);
  border: 2px solid rgba(148, 163, 184, 0.35);
  color: #94a3b8;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.workflow-step.is-active .step-circle {
  background: rgba(6, 182, 212, 0.15);
  border-color: #0891b2;
  color: #0891b2;
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
}

.workflow-step.is-completed .step-circle {
  background: #06b6d4;
  border-color: #06b6d4;
  color: white;
}

/* Step content */
.step-content {
  flex: 1;
  padding: 8px 10px;
  border-radius: 8px;
  transition: background 0.18s ease;
  min-width: 0;
}

.workflow-step.is-active .step-content {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.1), rgba(2, 132, 199, 0.05));
}

.step-label {
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  line-height: 1.3;
  transition: color 0.18s;
}

.workflow-step.is-active .step-label {
  color: #0891b2;
  font-weight: 600;
}

.workflow-step.is-completed .step-label {
  color: #0e7490;
}

.workflow-step.is-future .step-label {
  color: #94a3b8;
}

.step-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workflow-step.is-active .step-desc {
  color: #0891b2;
  opacity: 0.7;
}

/* ── Building Switcher ── */
.building-switcher {
  display: block;
  margin: 2px 4px 6px;
}

.building-switcher-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(241, 245, 249, 0.8), rgba(226, 232, 240, 0.4));
  border: 1px solid rgba(203, 213, 225, 0.45);
  cursor: pointer;
  transition: all 0.18s ease;
}

.building-switcher-trigger:hover {
  border-color: rgba(6, 182, 212, 0.45);
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.05), rgba(6, 182, 212, 0.02));
  box-shadow: 0 1px 4px rgba(6, 182, 212, 0.08);
}

.building-switcher-trigger .el-icon {
  color: #94a3b8;
  transition: transform 0.2s;
}

.building-switcher-trigger:hover .el-icon {
  color: #0891b2;
}

.building-switcher-trigger.static {
  cursor: default;
}
.building-switcher-trigger.static:hover {
  border-color: rgba(203, 213, 225, 0.45);
  background: linear-gradient(135deg, rgba(241, 245, 249, 0.8), rgba(226, 232, 240, 0.4));
  box-shadow: none;
}

.building-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.building-switcher :deep(.el-dropdown-menu__item.is-current) {
  color: #0891b2;
  font-weight: 600;
  background: rgba(6, 182, 212, 0.06);
}

@media (max-width: 768px) {
  .nav-item {
    padding: 12px 14px;
    font-size: 14px;
    -webkit-tap-highlight-color: transparent;
  }

  .workflow-step {
    padding-right: 4px;
  }

  .step-label {
    font-size: 14px;
  }

  .step-desc {
    font-size: 12px;
  }

  .sidebar-nav {
    padding: 16px 8px;
  }
}
</style>
