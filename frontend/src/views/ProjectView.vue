<script setup lang="ts">
import { onMounted, ref, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, VideoPlay, OfficeBuilding } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useTaskTrackerStore } from '@/stores/taskTracker'
import { getProject } from '@/api/projects'
import { createBuilding, deleteBuilding } from '@/api/buildings'
import { getSimulations, runLoadSimulation } from '@/api/simulation'
import type { SimulationResult } from '@/types/simulation'
import type { Project } from '@/types/project'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getClimateZone } from '@/data/regions'
import { useResponsive } from '@/composables/useResponsive'
import { createDefaultZone } from '@/utils/buildingDefaults'

const { isMobile } = useResponsive()

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const tracker = useTaskTrackerStore()
const { t } = useI18n()

const project = ref<Project | null>(null)
const projectId = route.params.projectId as string

// Simulation results per building
const simMap = reactive<Record<string, SimulationResult | null>>({})

async function fetchSimResults() {
  for (const b of store.buildings) {
    try {
      const { data } = await getSimulations(b.id)
      const completed = data.filter(r => r.status === 'completed')
      simMap[b.id] = completed.length > 0 ? completed[completed.length - 1] : null
    } catch {
      simMap[b.id] = null
    }
  }
}

function formatNum(val: number | null | undefined) {
  if (val == null) return '-'
  return val >= 1000 ? val.toFixed(0) : val.toFixed(1)
}

function getBuildingArea(b: { total_area?: number | null; zones?: { area: number }[] | null }): number | null {
  if (b.total_area && b.total_area > 0) return b.total_area
  if (b.zones && b.zones.length > 0) {
    const sum = b.zones.reduce((acc, z) => acc + (z.area || 0), 0)
    return sum > 0 ? sum : null
  }
  return null
}

function getZoneCount(b: { zones?: unknown[] | null }): number {
  return b.zones?.length || 0
}

function getCoolPerArea(b: { id: string; total_area?: number | null; zones?: { area: number }[] | null }): string {
  const sim = simMap[b.id]
  const area = getBuildingArea(b)
  if (!sim?.peak_cooling_load || !area) return '-'
  return ((sim.peak_cooling_load * 1000) / area).toFixed(1)
}

function getHeatPerArea(b: { id: string; total_area?: number | null; zones?: { area: number }[] | null }): string {
  const sim = simMap[b.id]
  const area = getBuildingArea(b)
  if (!sim?.peak_heating_load || !area) return '-'
  return ((sim.peak_heating_load * 1000) / area).toFixed(1)
}

watch(() => store.buildings, () => {
  if (store.buildings.length > 0) fetchSimResults()
})

onMounted(async () => {
  const { data } = await getProject(projectId)
  project.value = data
  store.setCurrentProject(data)
  await store.fetchBuildings(projectId)
})

async function handleAddBuilding() {
  const climate_zone = project.value?.location
    ? getClimateZone(project.value.location.split('-')[0])
    : undefined
  const baseName = t('building.defaultName')
  // Find next available number by scanning existing building names
  const nameRegex = new RegExp(`^${baseName}\\s*(\\d+)$`)
  let maxIdx = 0
  for (const b of store.buildings) {
    const m = (b.name || '').match(nameRegex)
    if (m) {
      const n = parseInt(m[1], 10)
      if (!Number.isNaN(n) && n > maxIdx) maxIdx = n
    }
  }
  const nextIdx = maxIdx + 1
  const defaultZoneName = `${t('building.zone.defaultPrefix')}1`
  const { data } = await createBuilding(projectId, {
    name: `${baseName} ${nextIdx}`,
    building_type: 'office',
    climate_zone,
    zones: [createDefaultZone(defaultZoneName)],
  })
  ElMessage.success(t('building.createSuccess'))
  await store.fetchBuildings(projectId)
  router.push(`/projects/${projectId}/buildings/${data.id}`)
}

async function handleDeleteBuilding(buildingId: string) {
  await ElMessageBox.confirm(t('building.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteBuilding(projectId, buildingId)
  ElMessage.success(t('building.deleteSuccess'))
  delete simMap[buildingId]
  await store.fetchBuildings(projectId)
}

function openBuilding(buildingId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}`)
}

// --- Batch Load Simulation ---
const runningBuildings = reactive<Set<string>>(new Set())

async function handleRunLoad(building: { id: string; name: string; zones?: unknown[] | null }) {
  if (!building.zones || building.zones.length === 0) {
    ElMessage.warning(t('building.noZonesWarning'))
    return
  }
  runningBuildings.add(building.id)
  try {
    const { data } = await runLoadSimulation(building.id)
    tracker.addTask({
      resultId: data.id,
      buildingId: building.id,
      buildingName: building.name,
      simulationType: 'load',
    })
    ElMessage.success(t('simulation.loadCalc.taskCreated'))
  } catch {
    ElMessage.error(t('simulation.loadCalc.failed'))
  } finally {
    runningBuildings.delete(building.id)
  }
}

async function handleRunAllLoads() {
  const buildings = store.buildings.filter(b => b.zones && b.zones.length > 0)
  if (buildings.length === 0) {
    ElMessage.warning(t('building.noZonesWarning'))
    return
  }
  for (const b of buildings) {
    await handleRunLoad(b)
  }
}
</script>

<template>
  <div class="project-view">
    <!-- Section: building list -->
    <div class="section-header">
      <div class="section-header-left">
        <h2>{{ t('building.title') }}</h2>
        <span class="section-hint">在此处管理项目下的所有建筑及其负荷仿真</span>
      </div>
      <div class="section-header-right">
        <el-button :icon="VideoPlay" @click="handleRunAllLoads" :disabled="store.buildings.length === 0">
          {{ t('building.runAllLoads') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="handleAddBuilding">
          {{ t('building.add') }}
        </el-button>
      </div>
    </div>

    <!-- Mobile: Card Layout -->
    <div v-if="isMobile" class="building-cards">
      <el-card
        v-for="row in store.buildings"
        :key="row.id"
        class="building-card"
        shadow="hover"
        @click="openBuilding(row.id)"
      >
        <div class="building-card-header">
          <span class="building-name">{{ row.name }}</span>
          <el-tag v-if="row.building_type" size="small" type="info">
            {{ t(`building.types.${row.building_type}`) }}
          </el-tag>
        </div>
        <div class="building-card-sim">
          <div class="sim-item">
            <span class="sim-label">建筑面积</span>
            <span class="sim-value">{{ formatNum(getBuildingArea(row)) }} m²</span>
          </div>
          <div class="sim-item">
            <span class="sim-label">{{ t('building.peakCooling') }}</span>
            <span class="sim-value">{{ formatNum(simMap[row.id]?.peak_cooling_load) }}</span>
          </div>
          <div class="sim-item">
            <span class="sim-label">{{ t('building.peakHeating') }}</span>
            <span class="sim-value">{{ formatNum(simMap[row.id]?.peak_heating_load) }}</span>
          </div>
        </div>
        <div class="building-card-actions" @click.stop>
          <el-button
            size="small"
            :icon="VideoPlay"
            :loading="runningBuildings.has(row.id)"
            @click.stop="handleRunLoad(row)"
          >
            {{ t('building.runLoad') }}
          </el-button>
          <el-button
            type="danger"
            size="small"
            text
            :icon="Delete"
            @click.stop="handleDeleteBuilding(row.id)"
          >
            {{ t('common.delete') }}
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- Desktop: Card Grid Layout -->
    <div v-else class="building-grid" v-loading="store.loading">
      <div
        v-for="row in store.buildings"
        :key="row.id"
        class="bcard"
        :class="{ 'bcard--dim': !simMap[row.id] }"
        @click="openBuilding(row.id)"
      >
        <div class="bcard-header">
          <div class="bcard-title">
            <div class="bcard-name-row">
              <span class="bcard-name">{{ row.name }}</span>
              <el-tag
                :type="simMap[row.id] ? 'success' : 'info'"
                size="small"
                effect="light"
                class="bcard-status"
              >
                {{ simMap[row.id] ? t('viz.hasResult') : t('building.noSimulation') }}
              </el-tag>
            </div>
            <div class="bcard-meta">
              <span class="meta-pill meta-pill--area">
                <el-icon class="meta-pill-icon"><OfficeBuilding /></el-icon>
                <span class="meta-pill-value">{{ formatNum(getBuildingArea(row)) }}</span>
                <span class="meta-pill-unit">m²</span>
              </span>
              <span class="meta-pill">
                <span class="meta-pill-value">{{ getZoneCount(row) }}</span>
                <span class="meta-pill-unit">个分区</span>
              </span>
              <el-tag v-if="row.building_type" size="small" type="info" effect="plain">
                {{ t(`building.types.${row.building_type}`) }}
              </el-tag>
              <el-tag v-if="row.floor_count" size="small" effect="plain">
                {{ row.floor_count }} 层
              </el-tag>
            </div>
          </div>
        </div>

        <div class="bcard-stats">
          <div class="stat-item stat-cool">
            <div class="stat-label">冷负荷峰值</div>
            <div class="stat-value">
              {{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_cooling_load) : '-' }}
              <span class="stat-unit">kW</span>
            </div>
          </div>
          <div class="stat-item stat-heat">
            <div class="stat-label">热负荷峰值</div>
            <div class="stat-value">
              {{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_heating_load) : '-' }}
              <span class="stat-unit">kW</span>
            </div>
          </div>
          <div class="stat-item stat-cool-soft">
            <div class="stat-label">冷负荷累计</div>
            <div class="stat-value">
              {{ simMap[row.id] ? formatNum(simMap[row.id]?.total_cooling_load) : '-' }}
              <span class="stat-unit">kWh</span>
            </div>
          </div>
          <div class="stat-item stat-heat-soft">
            <div class="stat-label">热负荷累计</div>
            <div class="stat-value">
              {{ simMap[row.id] ? formatNum(simMap[row.id]?.total_heating_load) : '-' }}
              <span class="stat-unit">kWh</span>
            </div>
          </div>
          <div class="stat-item stat-cool">
            <div class="stat-label">单位面积冷负荷</div>
            <div class="stat-value">
              {{ getCoolPerArea(row) }}
              <span class="stat-unit">W/m²</span>
            </div>
          </div>
          <div class="stat-item stat-heat">
            <div class="stat-label">单位面积热负荷</div>
            <div class="stat-value">
              {{ getHeatPerArea(row) }}
              <span class="stat-unit">W/m²</span>
            </div>
          </div>
        </div>

        <div class="bcard-actions" @click.stop>
          <el-button
            size="small"
            :icon="VideoPlay"
            :loading="runningBuildings.has(row.id)"
            @click.stop="handleRunLoad(row)"
          >
            {{ t('building.runLoad') }}
          </el-button>
          <el-button type="primary" size="small" @click.stop="openBuilding(row.id)">
            {{ t('building.config') }}
          </el-button>
          <el-button
            type="danger"
            size="small"
            text
            :icon="Delete"
            @click.stop="handleDeleteBuilding(row.id)"
          >
            {{ t('common.delete') }}
          </el-button>
        </div>
      </div>
    </div>

    <el-empty v-if="!store.loading && store.buildings.length === 0" :description="t('building.noBuildings')">
      <el-button type="primary" :icon="Plus" @click="handleAddBuilding">
        {{ t('building.add') }}
      </el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.project-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Hero header */
.project-hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  padding: 28px 32px;
  background: linear-gradient(135deg, #ecfeff 0%, #f0f9ff 50%, #faf5ff 100%);
  border: 1px solid rgba(8, 145, 178, 0.12);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.project-hero-content {
  position: relative;
  z-index: 1;
}
.project-hero-decor {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(8, 145, 178, 0.18), rgba(124, 58, 237, 0.08) 60%, transparent 70%);
  pointer-events: none;
}
.hero-eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0891b2;
  margin-bottom: 8px;
}
.hero-title {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.hero-desc {
  color: #475569;
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.6;
  max-width: 720px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(8, 145, 178, 0.2);
  color: #0e7490;
  font-size: 13px;
  font-weight: 500;
  backdrop-filter: blur(6px);
}
.meta-chip--soft {
  border-color: rgba(124, 58, 237, 0.18);
  color: #6d28d9;
}
.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

/* Section header */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}
.section-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.section-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
}
.section-hint {
  font-size: 13px;
  color: #94a3b8;
}
.section-header-right {
  display: flex;
  gap: 8px;
}

/* Desktop card grid */
.building-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}
.bcard {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.bcard:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 36px rgba(8, 145, 178, 0.14), 0 4px 10px rgba(15, 23, 42, 0.06);
  border-color: rgba(8, 145, 178, 0.45);
}
.bcard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}
.bcard-title {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  width: 100%;
}
.bcard-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.bcard-name {
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}
.bcard-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px;
  border-radius: 999px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #475569;
  line-height: 1.2;
}
.meta-pill--area {
  background: linear-gradient(135deg, #f5f3ff, #faf5ff);
  border-color: rgba(124, 58, 237, 0.22);
  color: #6d28d9;
}
.meta-pill-icon {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  color: #7c3aed;
  opacity: 0.9;
}
.meta-pill-value {
  font-weight: 700;
  color: #0f172a;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.meta-pill-unit {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 1px;
}
.bcard-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
/* Dimmed card for unsimulated buildings */
.bcard--dim .bcard-stats .stat-item {
  background: #f8fafc !important;
  border-color: #e5e7eb !important;
  opacity: 0.72;
}
.bcard--dim .bcard-stats .stat-item .stat-unit {
  visibility: hidden;
}
.bcard--dim .bcard-stats .stat-item .stat-value {
  color: #94a3b8;
}
.bcard-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.stat-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.stat-cool {
  background: linear-gradient(135deg, #ecfeff 0%, #f0f9ff 100%);
}
.stat-heat {
  background: linear-gradient(135deg, #fff7ed 0%, #fef2f2 100%);
}
.stat-cool-soft {
  background: linear-gradient(135deg, #f0f9ff 0%, #fafbff 100%);
}
.stat-heat-soft {
  background: linear-gradient(135deg, #fff7ed 0%, #fffaf5 100%);
}
.stat-area {
  background: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 100%);
}
.stat-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.stat-unit {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  margin-left: 2px;
}
.bcard-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 4px;
}
.project-view :deep(.el-empty) {
  padding: 60px 0;
  background: #ffffff;
  border-radius: 12px;
  border: 1px dashed #e2e8f0;
}

@media (max-width: 768px) {
  .project-hero {
    padding: 22px 20px;
  }
  .hero-title {
    font-size: 20px;
  }
  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .section-header-right {
    width: 100%;
  }
  .section-header-right .el-button {
    flex: 1;
  }

  .building-cards {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .building-card {
    cursor: pointer;
    border-radius: 12px;
  }
  .building-card :deep(.el-card__body) {
    padding: 14px;
  }
  .building-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
  }
  .building-name {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
    flex: 1;
    margin-right: 8px;
  }
  .building-tags {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .building-card-sim {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    padding: 8px 0;
    border-top: 1px solid #f0f0f0;
  }
  .sim-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .sim-label {
    font-size: 12px;
    color: #94a3b8;
  }
  .sim-value {
    font-size: 14px;
    font-weight: 600;
    color: #334155;
  }
  .building-card-actions {
    display: flex;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px solid #f0f0f0;
  }
}
</style>
