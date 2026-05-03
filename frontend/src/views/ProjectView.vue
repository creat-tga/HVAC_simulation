<script setup lang="ts">
import { computed, onMounted, ref, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Delete, Edit, Sunny, CopyDocument, OfficeBuilding } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useTaskTrackerStore } from '@/stores/taskTracker'
import { getProject } from '@/api/projects'
import { createBuilding, deleteBuilding, getBuilding, updateBuilding } from '@/api/buildings'
import { getSimulations, runLoadSimulation } from '@/api/simulation'
import AddWorkspaceItemIcon from '@/components/icons/AddWorkspaceItemIcon.vue'
import StartSimulationIcon from '@/components/icons/StartSimulationIcon.vue'
import type { SimulationResult } from '@/types/simulation'
import type { Project } from '@/types/project'
import type { Building, BuildingCreate } from '@/types/building'
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
const MAX_BUILDINGS_PER_PROJECT = 10
const isBuildingLimitReached = computed(() => store.buildings.length >= MAX_BUILDINGS_PER_PROJECT)
const copyingBuildings = reactive<Set<string>>(new Set())

// Simulation results per building
const simMap = reactive<Record<string, SimulationResult | null>>({})
const simStatusMap = reactive<Record<string, string | null>>({})

async function fetchSimResults() {
  for (const b of store.buildings) {
    try {
      const { data } = await getSimulations(b.id, 'load')
      const latest = data[0] || null
      simStatusMap[b.id] = latest?.status || null
      simMap[b.id] = latest?.status === 'completed' ? latest : null
    } catch {
      simStatusMap[b.id] = null
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

function getBuildingSummary(b: { total_area?: number | null; zones?: { area: number }[] | null }): string {
  return `${formatNum(getBuildingArea(b))}㎡(${getZoneCount(b)}个分区)`
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

// Auto-refresh simulation results in the building list when any task completes.
// Tracks the number of completed/failed tasks; whenever it grows, refresh.
const _completedSeen = ref(0)
watch(
  () => tracker.completedTasks.length,
  (n) => {
    if (n > _completedSeen.value) {
      _completedSeen.value = n
      fetchSimResults()
    }
  }
)

onMounted(async () => {
  const { data } = await getProject(projectId)
  project.value = data
  store.setCurrentProject(data)
  await store.fetchBuildings(projectId)
})

const addDialogVisible = ref(false)
const addSubmitting = ref(false)
const addForm = reactive<{ name: string }>({
  name: '',
})

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function getNextBuildingName(): string {
  const baseName = t('building.defaultName')
  const nameRegex = new RegExp(`^${escapeRegExp(baseName)}\\s*(\\d+)$`)
  let maxIdx = 0
  for (const b of store.buildings) {
    const m = (b.name || '').match(nameRegex)
    if (m) {
      const n = parseInt(m[1], 10)
      if (!Number.isNaN(n) && n > maxIdx) maxIdx = n
    }
  }
  return `${baseName} ${maxIdx + 1}`
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function getCopyName(name: string, existingNames: string[]): string {
  const names = new Set(existingNames)
  const baseName = `${name}（副本）`
  if (!names.has(baseName)) return baseName
  let idx = 2
  while (names.has(`${name}（副本${idx}）`)) idx += 1
  return `${name}（副本${idx}）`
}

function handleAddBuilding() {
  if (isBuildingLimitReached.value) {
    ElMessage.info(t('building.limitReached', { max: MAX_BUILDINGS_PER_PROJECT }))
    return
  }
  addForm.name = getNextBuildingName()
  addDialogVisible.value = true
}

async function confirmAddBuilding() {
  if (isBuildingLimitReached.value) {
    ElMessage.info(t('building.limitReached', { max: MAX_BUILDINGS_PER_PROJECT }))
    return
  }
  const name = addForm.name.trim()
  if (!name) {
    ElMessage.warning(t('building.pleaseInputName'))
    return
  }
  const climate_zone = project.value?.location
    ? getClimateZone(project.value.location.split('-')[0])
    : undefined
  const defaultZoneName = `${t('building.zone.defaultPrefix')}1`
  addSubmitting.value = true
  try {
    const { data } = await createBuilding(projectId, {
      name,
      building_type: 'office',
      climate_zone,
      zones: [createDefaultZone(defaultZoneName)],
    })
    ElMessage.success(t('building.createSuccess'))
    addDialogVisible.value = false
    await store.fetchBuildings(projectId)
    router.push(`/projects/${projectId}/buildings/${data.id}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  } finally {
    addSubmitting.value = false
  }
}

async function handleDeleteBuilding(buildingId: string) {
  await ElMessageBox.confirm(t('building.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteBuilding(projectId, buildingId)
  ElMessage.success(t('building.deleteSuccess'))
  delete simMap[buildingId]
  await store.fetchBuildings(projectId)
}

async function copyBuilding(row: Building, event?: MouseEvent) {
  event?.stopPropagation()
  if (isBuildingLimitReached.value) {
    ElMessage.info(t('building.limitReached', { max: MAX_BUILDINGS_PER_PROJECT }))
    return
  }
  if (copyingBuildings.has(row.id)) return

  copyingBuildings.add(row.id)
  try {
    const { data: source } = await getBuilding(projectId, row.id)
    const payload: BuildingCreate = {
      name: getCopyName(source.name, store.buildings.map((b) => b.name)),
      building_type: source.building_type || 'office',
    }
    if (source.total_area !== null) payload.total_area = source.total_area
    if (source.floor_count !== null) payload.floor_count = source.floor_count
    if (source.location !== null) payload.location = source.location
    if (source.climate_zone !== null) payload.climate_zone = source.climate_zone
    if (source.envelope_params !== null) payload.envelope_params = cloneJson(source.envelope_params)
    if (source.zones !== null) payload.zones = cloneJson(source.zones)

    await createBuilding(projectId, payload)
    await store.fetchBuildings(projectId)
    await fetchSimResults()
    ElMessage.success('建筑已复制')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  } finally {
    copyingBuildings.delete(row.id)
  }
}

const editDialogVisible = ref(false)
const editForm = reactive<{ id: string; name: string }>({
  id: '',
  name: '',
})

function openEditDialog(row: Building, event?: MouseEvent) {
  event?.stopPropagation()
  editForm.id = row.id
  editForm.name = row.name
  editDialogVisible.value = true
}

async function confirmEdit() {
  const name = editForm.name.trim()
  if (!name) {
    ElMessage.warning(t('building.pleaseInputName'))
    return
  }
  try {
    await updateBuilding(projectId, editForm.id, { name })
    editDialogVisible.value = false
    await store.fetchBuildings(projectId)
    ElMessage.success(t('building.updateSuccess'))
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  }
}

function openBuilding(buildingId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}`)
}

// --- Batch Load Simulation ---
const runningBuildings = reactive<Set<string>>(new Set())
const batchLoadSubmitting = ref(false)
const hasActiveLoadTask = computed(() =>
  tracker.activeTasks.some(task => task.simulationType === 'load')
)
const isLoadBatchBusy = computed(() => batchLoadSubmitting.value || hasActiveLoadTask.value)

function hasZones(building: { zones?: unknown[] | null }): boolean {
  return Boolean(building.zones && building.zones.length > 0)
}

function isBuildingLoadRunning(buildingId: string): boolean {
  return runningBuildings.has(buildingId)
    || ['pending', 'running'].includes(simStatusMap[buildingId] || '')
    || tracker.activeTasks.some(task => task.simulationType === 'load' && task.buildingId === buildingId)
}

function needsLoadSimulation(building: { id: string; zones?: unknown[] | null }): boolean {
  return hasZones(building) && !simMap[building.id] && !isBuildingLoadRunning(building.id)
}

async function submitLoadSimulation(building: { id: string; name: string; zones?: unknown[] | null }) {
  if (!hasZones(building)) {
    ElMessage.warning(t('building.noZonesWarning'))
    return false
  }
  if (isBuildingLoadRunning(building.id)) {
    return false
  }
  runningBuildings.add(building.id)
  try {
    const { data } = await runLoadSimulation(building.id)
    simStatusMap[building.id] = data.status
    tracker.addTask({
      resultId: data.id,
      buildingId: building.id,
      buildingName: building.name,
      simulationType: 'load',
    })
    return true
  } catch {
    return false
  } finally {
    runningBuildings.delete(building.id)
  }
}

async function handleRunAllLoads() {
  if (isLoadBatchBusy.value) {
    ElMessage.warning(t('building.loadBatchRunning'))
    return
  }

  const runnableBuildings = store.buildings.filter(hasZones)
  if (runnableBuildings.length === 0) {
    ElMessage.warning(t('building.noZonesWarning'))
    return
  }

  const buildings = runnableBuildings.filter(needsLoadSimulation)
  if (buildings.length === 0) {
    ElMessage.info(t('building.noPendingLoadBuildings'))
    return
  }

  batchLoadSubmitting.value = true
  let submittedCount = 0
  try {
    for (const b of buildings) {
      if (await submitLoadSimulation(b)) submittedCount += 1
    }
  } finally {
    batchLoadSubmitting.value = false
  }

  if (submittedCount > 0) {
    ElMessage.success(t('building.loadBatchSubmitted', { count: submittedCount }))
  }
  if (submittedCount < buildings.length) {
    ElMessage.error(t('building.loadBatchPartialFailed', {
      failed: buildings.length - submittedCount,
    }))
  }
}
</script>

<template>
  <div class="project-view">
    <!-- Section: building list -->
    <div v-if="!isMobile" class="section-header">
      <div class="section-header-left">
        <h2>{{ t('building.title') }}</h2>
        <span class="section-hint">在此处管理项目下的所有建筑及其负荷仿真</span>
      </div>
      <div class="section-header-right">
        <el-button
          :icon="StartSimulationIcon"
          :loading="batchLoadSubmitting"
          @click="handleRunAllLoads"
          :disabled="store.buildings.length === 0 || isLoadBatchBusy"
        >
          {{ t('building.runAllLoads') }}
        </el-button>
        <el-button
          type="primary"
          :icon="AddWorkspaceItemIcon"
          :disabled="isBuildingLimitReached"
          :title="isBuildingLimitReached ? t('building.limitReached', { max: MAX_BUILDINGS_PER_PROJECT }) : t('building.add')"
          @click="handleAddBuilding"
        >
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
        :class="{ 'building-card--dim': !simMap[row.id] }"
        shadow="hover"
        @click="openBuilding(row.id)"
      >
        <div class="building-card-header">
          <div class="building-title-line">
            <span class="building-title-mark"><el-icon><OfficeBuilding /></el-icon></span>
            <div class="building-title-text">
              <span class="building-name">{{ row.name }}</span>
              <span class="building-summary">{{ getBuildingSummary(row) }}</span>
            </div>
          </div>
          <div class="building-card-actions" @click.stop>
            <el-button
              class="building-action-button"
              type="primary"
              text
              circle
              :icon="CopyDocument"
              :loading="copyingBuildings.has(row.id)"
              @click="copyBuilding(row, $event)"
              title="复制建筑"
            />
            <el-button
              class="building-action-button"
              type="primary"
              text
              circle
              :icon="Edit"
              @click="openEditDialog(row, $event)"
              :title="t('common.edit') || '编辑'"
            />
            <el-button
              class="building-action-button"
              type="danger"
              text
              circle
              :icon="Delete"
              @click="handleDeleteBuilding(row.id)"
              :title="t('common.delete')"
            />
          </div>
        </div>

        <div v-if="row.floor_count" class="building-card-meta">
          <el-tag v-if="row.floor_count" size="small" effect="plain">
            {{ row.floor_count }} 层
          </el-tag>
        </div>

        <div class="building-metric-panels">
          <div class="metric-panel metric-panel--cool">
            <div class="metric-panel-title">
              <span class="metric-panel-symbol metric-panel-symbol--snow" aria-hidden="true">❄</span>
              <span>制冷</span>
            </div>
            <div class="metric-row"><span>峰值负荷</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_cooling_load) : '-' }} <em>kW</em></strong></div>
            <div class="metric-row"><span>累计值</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.total_cooling_load) : '-' }} <em>kWh</em></strong></div>
            <div class="metric-row"><span>冷指标</span><strong>{{ getCoolPerArea(row) }} <em>W/m²</em></strong></div>
          </div>
          <div class="metric-panel metric-panel--heat">
            <div class="metric-panel-title">
              <span class="metric-panel-symbol"><el-icon><Sunny /></el-icon></span>
              <span>制热</span>
            </div>
            <div class="metric-row"><span>峰值负荷</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_heating_load) : '-' }} <em>kW</em></strong></div>
            <div class="metric-row"><span>累计值</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.total_heating_load) : '-' }} <em>kWh</em></strong></div>
            <div class="metric-row"><span>热指标</span><strong>{{ getHeatPerArea(row) }} <em>W/m²</em></strong></div>
          </div>
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
              <div class="bcard-name-main">
                <div class="building-title-line">
                  <span class="building-title-mark"><el-icon><OfficeBuilding /></el-icon></span>
                  <div class="building-title-text">
                    <span class="bcard-name">{{ row.name }}</span>
                    <span class="building-summary">{{ getBuildingSummary(row) }}</span>
                  </div>
                </div>
              </div>
              <div class="bcard-card-actions" @click.stop>
                <el-button
                  class="building-action-button"
                  type="primary"
                  :icon="CopyDocument"
                  :loading="copyingBuildings.has(row.id)"
                  text
                  @click="copyBuilding(row, $event)"
                  title="复制建筑"
                />
                <el-button
                  class="building-action-button"
                  type="primary"
                  :icon="Edit"
                  text
                  @click="openEditDialog(row, $event)"
                  :title="t('common.edit') || '编辑'"
                />
                <el-button
                  class="building-action-button"
                  type="danger"
                  :icon="Delete"
                  text
                  @click="handleDeleteBuilding(row.id)"
                  :title="t('common.delete')"
                />
              </div>
            </div>
            <div v-if="row.floor_count" class="bcard-meta">
              <el-tag v-if="row.floor_count" size="small" effect="plain">
                {{ row.floor_count }} 层
              </el-tag>
            </div>
          </div>
        </div>

        <div class="building-metric-panels">
          <div class="metric-panel metric-panel--cool">
            <div class="metric-panel-title">
              <span class="metric-panel-symbol metric-panel-symbol--snow" aria-hidden="true">❄</span>
              <span>制冷</span>
            </div>
            <div class="metric-row"><span>峰值负荷</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_cooling_load) : '-' }} <em>kW</em></strong></div>
            <div class="metric-row"><span>累计值</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.total_cooling_load) : '-' }} <em>kWh</em></strong></div>
            <div class="metric-row"><span>冷指标</span><strong>{{ getCoolPerArea(row) }} <em>W/m²</em></strong></div>
          </div>
          <div class="metric-panel metric-panel--heat">
            <div class="metric-panel-title">
              <span class="metric-panel-symbol"><el-icon><Sunny /></el-icon></span>
              <span>制热</span>
            </div>
            <div class="metric-row"><span>峰值负荷</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.peak_heating_load) : '-' }} <em>kW</em></strong></div>
            <div class="metric-row"><span>累计值</span><strong>{{ simMap[row.id] ? formatNum(simMap[row.id]?.total_heating_load) : '-' }} <em>kWh</em></strong></div>
            <div class="metric-row"><span>热指标</span><strong>{{ getHeatPerArea(row) }} <em>W/m²</em></strong></div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="!store.loading && store.buildings.length === 0" :description="t('building.noBuildings')">
      <el-button type="primary" :icon="AddWorkspaceItemIcon" @click="handleAddBuilding">
        {{ t('building.add') }}
      </el-button>
    </el-empty>

    <el-dialog v-model="addDialogVisible" :title="t('building.createDialogTitle')" width="420px" append-to-body>
      <el-form label-width="96px" @submit.prevent>
        <el-form-item :label="t('building.name')" required>
          <el-input
            v-model="addForm.name"
            :maxlength="30"
            show-word-limit
            :placeholder="t('building.pleaseInputName')"
            @keyup.enter="confirmAddBuilding"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="addSubmitting" @click="addDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="addSubmitting" @click="confirmAddBuilding">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" :title="t('building.editInfo')" width="420px" append-to-body>
      <el-form label-width="96px">
        <el-form-item :label="t('building.name')" required>
          <el-input v-model="editForm.name" :maxlength="30" show-word-limit :placeholder="t('building.pleaseInputName')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmEdit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <Teleport to="body">
      <!-- 移动端底部固定主操作栏 -->
      <div v-if="isMobile" class="mobile-action-bar">
        <el-button
          class="mab-btn mab-btn--simulate"
          :loading="batchLoadSubmitting"
          :disabled="store.buildings.length === 0 || isLoadBatchBusy"
          @click="handleRunAllLoads"
        >
          <span class="mab-icon" aria-hidden="true">
            <el-icon><StartSimulationIcon /></el-icon>
          </span>
          <span class="mab-title">仿真</span>
        </el-button>
        <el-button
          class="mab-btn mab-btn--create"
          @click="handleAddBuilding"
        >
          <span class="mab-icon" aria-hidden="true">
            <el-icon><AddWorkspaceItemIcon /></el-icon>
          </span>
          <span class="mab-title">新增</span>
        </el-button>
      </div>
    </Teleport>
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
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: 16px;
  min-width: 0;
}
.bcard {
  display: flex;
  flex-direction: column;
  gap: var(--sim-card-gap);
  padding: var(--sim-card-padding);
  border-radius: var(--sim-card-radius);
  background: var(--sim-card-bg);
  border: 1px solid var(--sim-card-border);
  box-shadow: var(--sim-card-shadow);
  cursor: pointer;
  min-width: 0;
  overflow: hidden;
  transition: var(--sim-card-transition);
}
.bcard:hover {
  transform: var(--sim-card-hover-transform);
  box-shadow: var(--sim-card-hover-shadow);
  border-color: var(--sim-card-hover-border);
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
  overflow: hidden;
}
.bcard-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}
.bcard-name-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1 1 0;
  overflow: hidden;
}
.building-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
}
.building-title-mark {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: #2563eb;
  background: linear-gradient(135deg, #eff6ff, #eef2ff);
  font-size: 22px;
}
.building-title-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
  flex: 1 1 0;
  overflow: hidden;
}
.bcard-name {
  display: block;
  font-size: 16px;
  font-weight: 500;
  color: var(--sim-card-title);
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.building-summary {
  display: block;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.2;
  color: var(--sim-card-subtitle);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.building-action-button {
  min-width: 34px;
  width: 34px;
  height: 34px;
  padding: 0;
}
.project-view :deep(.building-action-button .el-icon) {
  font-size: 18px;
}
.bcard-card-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex: 0 0 auto;
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
.bcard--dim .metric-panel,
.building-card--dim .metric-panel {
  background: var(--sim-metric-dim-bg);
  opacity: 0.78;
}
.bcard--dim .metric-row strong,
.building-card--dim .metric-row strong {
  color: var(--sim-metric-dim-value);
}
.building-metric-panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.metric-panel {
  padding: 10px 8px;
  border-radius: 8px;
  border: 1px solid var(--sim-card-border);
  min-width: 0;
}
.metric-panel--cool {
  background: var(--sim-metric-cool-bg);
  border-color: var(--sim-metric-cool-border);
}
.metric-panel--heat {
  background: var(--sim-metric-heat-bg);
  border-color: var(--sim-metric-heat-border);
}
.metric-panel-title {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 8px;
  color: var(--sim-card-title);
  font-size: 12px;
  font-weight: 400;
  line-height: 1;
  white-space: nowrap;
}
.metric-panel-symbol {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--sim-metric-cool-icon-color);
  background: var(--sim-metric-cool-icon-bg);
}
.metric-panel-symbol--snow {
  color: var(--sim-metric-cool-icon-color);
  background: var(--sim-metric-cool-icon-bg);
  font-size: 15px;
  font-weight: 600;
  line-height: 1;
}
.metric-panel--heat .metric-panel-symbol {
  color: var(--sim-metric-heat-icon-color);
  background: var(--sim-metric-heat-icon-bg);
}
.metric-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 5px;
  min-width: 0;
  color: var(--sim-metric-text);
  font-size: 11px;
  line-height: 1.55;
}
.metric-row span {
  color: var(--sim-metric-text);
  font-weight: 500;
  white-space: nowrap;
}
.metric-row strong {
  min-width: 0;
  color: var(--sim-metric-value);
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metric-row em {
  color: var(--sim-metric-unit);
  font-size: 10px;
  font-style: normal;
  font-weight: 500;
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
    flex-direction: row;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
  }
  .section-header-right {
    width: auto;
    gap: 8px;
  }
  .section-header-right .el-button {
    flex: 0 0 auto;
  }

  .building-cards {
    padding: 0 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .building-card {
    --el-card-border-radius: var(--sim-card-radius);
    cursor: pointer;
    border-radius: var(--sim-card-radius) !important;
    background: var(--sim-card-bg);
    border: 1px solid var(--sim-card-border) !important;
    box-shadow: var(--sim-card-shadow) !important;
    overflow: hidden;
    transition: var(--sim-card-transition);
  }
  .building-card.el-card,
  .building-card :deep(.el-card) {
    --el-card-border-radius: var(--sim-card-radius);
    border-radius: var(--sim-card-radius) !important;
  }
  .building-card:hover {
    transform: var(--sim-card-hover-transform);
    border-color: var(--sim-card-hover-border) !important;
    box-shadow: var(--sim-card-hover-shadow) !important;
  }
  .building-card :deep(.el-card__body) {
    padding: var(--sim-card-mobile-padding);
  }
  .building-card-header {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    min-width: 0;
  }
  .building-card-actions {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    margin-left: auto;
    flex: 0 0 auto;
  }
  .building-name {
    display: block;
    font-size: 16px;
    font-weight: var(--font-weight-regular);
    color: #1e293b;
    flex: 0 1 auto;
    margin-right: 0;
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .building-title-mark {
    width: 38px;
    height: 38px;
    font-size: 20px;
  }
  .building-tags {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .building-card-sim {
    display: flex;
    gap: 16px;
    padding: 8px 0 0;
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

  /* 与桌面 bcard 一致的元数据/统计样式（移动端复用） */
  .building-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    margin-bottom: 10px;
  }
  .meta-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--surface-sunken, #f1f5f9);
    color: var(--text-secondary, #475569);
    font-size: 12px;
    line-height: 1.4;
  }
  .meta-pill--area {
    background: var(--brand-primary-soft, rgba(59, 130, 246, 0.1));
    color: var(--brand-primary, #3b82f6);
  }
  .meta-pill-icon { font-size: 12px; }
  .meta-pill-value { font-weight: 600; }
  .meta-pill-unit { opacity: 0.75; font-size: 11px; }

  .building-card-stats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .building-card-stats .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    gap: 2px;
    padding: 8px 8px;
    border-radius: 10px;
    background: var(--surface-sunken, #f8fafc);
    text-align: center;
    min-width: 0;
  }
  .building-card-stats .stat-item.stat-cool { background: rgba(59, 130, 246, 0.08); }
  .building-card-stats .stat-item.stat-heat { background: rgba(249, 115, 22, 0.08); }
  .building-card-stats .stat-item.stat-cool-soft { background: rgba(59, 130, 246, 0.04); }
  .building-card-stats .stat-item.stat-heat-soft { background: rgba(249, 115, 22, 0.04); }
  .building-card-stats .stat-label {
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    /* 自适应换行：CJK 默认按字符可断 */
    white-space: normal;
    word-break: break-word;
    overflow-wrap: anywhere;
    line-height: 1.25;
    text-align: center;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .building-card-stats .stat-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary, #1e293b);
    display: inline-flex;
    align-items: baseline;
    justify-content: center;
    gap: 3px;
    white-space: nowrap;
  }
  .building-card-stats .stat-unit {
    font-size: 10px;
    font-weight: 400;
    color: var(--text-muted, #94a3b8);
  }
  .building-card--dim { opacity: 0.92; }
  .building-metric-panels {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .metric-panel { padding: 10px 8px; }
  .metric-panel-title {
    align-items: center;
    flex-wrap: nowrap;
    gap: 5px;
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 400;
    line-height: 1;
  }
  .metric-panel-symbol {
    width: 20px;
    height: 20px;
    font-size: 12px;
  }
  .metric-row {
    gap: 5px;
    font-size: 11px;
    line-height: 1.55;
  }
  .metric-row span { font-weight: 500; }
  .metric-row strong { font-size: 12px; font-weight: 600; }
  .metric-row em { font-size: 10px; }

  /* 移动端底部固定主操作栏（位于 stage tab bar 上方） */
  .project-view { padding-bottom: 12px; }
}
</style>
