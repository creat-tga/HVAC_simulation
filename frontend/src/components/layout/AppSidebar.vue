<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'
import {
  HomeFilled,
  OfficeBuilding,
  ArrowDown,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useProjectStore()

const projectId = computed(() => route.params.projectId as string | undefined)
const buildingId = computed(() => route.params.buildingId as string | undefined)
const resultId = computed(() => route.params.resultId as string | undefined)

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
  else router.push(base)
}
</script>

<template>
  <el-aside width="220px" class="app-sidebar">
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

      <!-- Group 2: Building Design (only when in building context) -->
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

          <!-- Building Sub-items (workflow steps) -->
          <div
            class="nav-item sub-item"
            :class="{ 'is-active': isActive('building') }"
            @click="navigate(`/projects/${projectId}/buildings/${buildingId}`)"
          >
            <span class="step-badge">1</span>
            <span>{{ t('nav.buildingConfig') }}</span>
          </div>
          <div
            class="nav-item sub-item"
            :class="{ 'is-active': isActive('loadCalc') }"
            @click="navigate(`/projects/${projectId}/buildings/${buildingId}/load`)"
          >
            <span class="step-badge">2</span>
            <span>{{ t('nav.loadWeather') }}</span>
          </div>
          <div
            class="nav-item sub-item"
            :class="{ 'is-active': isActive('systemSelect') }"
            @click="navigate(`/projects/${projectId}/buildings/${buildingId}/system`)"
          >
            <span class="step-badge">3</span>
            <span>{{ t('nav.systemSelect') }}</span>
          </div>
        </div>

        <!-- Group 3: Simulation Results -->
        <div class="nav-group">
          <div class="nav-group-title">{{ t('nav.groupResult') }}</div>
          <div
            class="nav-item"
            :class="{ 'is-active': isActive('simulation') }"
            @click="navigate(`/projects/${projectId}/buildings/${buildingId}/simulation`)"
          >
            <span class="step-badge">4</span>
            <span>{{ t('nav.simulation') }}</span>
          </div>
          <div
            v-if="resultId"
            class="nav-item"
            :class="{ 'is-active': isActive('report') }"
            @click="navigate(`/projects/${projectId}/buildings/${buildingId}/report/${resultId}`)"
          >
            <span class="step-badge">5</span>
            <span>{{ t('nav.report') }}</span>
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

.nav-item.sub-item {
  padding-left: 28px;
  font-size: 13px;
  padding-top: 7px;
  padding-bottom: 7px;
}

.nav-item.sub-item.is-active {
  box-shadow: inset 3px 0 0 #06b6d4;
}

/* ── Step Badge ── */
.step-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  transition: all 0.18s ease;
}

.nav-item.is-active .step-badge {
  background: rgba(8, 145, 178, 0.15);
  color: #0891b2;
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

  .nav-item.sub-item {
    padding: 10px 14px 10px 28px;
    font-size: 14px;
  }

  .sidebar-nav {
    padding: 16px 8px;
  }
}
</style>
