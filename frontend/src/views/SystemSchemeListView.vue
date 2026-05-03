<script setup lang="ts">
/**
 * SystemSchemeListView — 项目级"方案列表"主页面（建筑搭建风格）.
 *
 * 功能：
 *   - Hero header + section header（新建方案 / 批量运行能耗仿真）
 *   - 方案卡片（建筑卡片风格）：名称 + 状态标签 + meta-pills + 9 宫指标 + 操作栏
 *   - 默认命名：方案 1 / 方案 2 / ...
 *   - 新建：选择已完成负荷仿真的建筑
 *   - 运行能耗仿真：占位（敬请期待）
 *   - 删除：二次确认
 */

import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete,
  Edit,
  Tickets,
  Sunny,
  CopyDocument,
} from '@element-plus/icons-vue'
import { useSystemSchemeStore } from '@/stores/system-scheme'
import { useProjectStore } from '@/stores/project'
import { useResponsive } from '@/composables/useResponsive'
import { getSimulations } from '@/api/simulation'
import { getScheme, updateScheme } from '@/api/system-scheme'
import AddWorkspaceItemIcon from '@/components/icons/AddWorkspaceItemIcon.vue'
import StartSimulationIcon from '@/components/icons/StartSimulationIcon.vue'
import type { Subsystem, SystemSchemeCreate } from '@/types/system-scheme'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useSystemSchemeStore()
const projectStore = useProjectStore()
const { isMobile } = useResponsive()

const projectId = computed(() => route.params.projectId as string)
const copyingSchemes = ref<Set<string>>(new Set())

// ------- 建筑候选（仅展示已完成负荷仿真的建筑作为可绑定项）-------
interface BuildingOpt {
  id: string
  name: string
  area: number | null
  hasLoad: boolean
}
const buildingOpts = ref<BuildingOpt[]>([])
const loadingBuildings = ref(false)

async function loadBuildings() {
  loadingBuildings.value = true
  try {
    if (!projectStore.buildings.length) {
      await projectStore.fetchBuildings(projectId.value)
    }
    const opts: BuildingOpt[] = []
    for (const b of projectStore.buildings) {
      try {
        const { data } = await getSimulations(b.id)
        const done = data.filter(
          (r) => r.status === 'completed' && r.simulation_type === 'load',
        )
        opts.push({ id: b.id, name: b.name, area: b.total_area ?? null, hasLoad: done.length > 0 })
      } catch {
        opts.push({ id: b.id, name: b.name, area: b.total_area ?? null, hasLoad: false })
      }
    }
    buildingOpts.value = opts
  } finally {
    loadingBuildings.value = false
  }
}

const buildingsWithLoad = computed(() => buildingOpts.value.filter((b) => b.hasLoad))

// ------- 新建方案对话框 -------
const newDialogVisible = ref(false)
const newForm = reactive<{ name: string; building_id: string | null }>({
  name: '',
  building_id: null,
})

const editDialogVisible = ref(false)
const editForm = reactive<{ id: string; name: string; safety_margin: number }>({
  id: '',
  name: '',
  safety_margin: 1.0,
})

function openNewDialog() {
  if (store.items.length >= 5) {
    ElMessage.warning(t('scheme.maxReached'))
    return
  }
  if (!buildingsWithLoad.value.length) {
    ElMessage.warning(t('scheme.noBuildingWithLoad'))
    return
  }
  // 默认命名：方案 N
  const nextIdx = store.items.length + 1
  newForm.name = t('scheme.defaultName', { n: nextIdx })
  newForm.building_id = buildingsWithLoad.value[0]?.id || null
  newDialogVisible.value = true
}

async function confirmNew() {
  if (!newForm.name.trim()) {
    ElMessage.warning(t('scheme.namePlaceholder'))
    return
  }
  if (!newForm.building_id) {
    ElMessage.warning(t('scheme.bindBuildingRequired'))
    return
  }
  const payload: SystemSchemeCreate = {
    name: newForm.name.trim(),
    building_id: newForm.building_id,
    scheme_index: store.items.length + 1,
    safety_margin: 1.0,
    subsystems: [],
  }
  try {
    const scheme = await store.add(projectId.value, payload)
    newDialogVisible.value = false
    ElMessage.success(t('common.created'))
    router.push(`/projects/${projectId.value}/system-schemes/${scheme.id}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  }
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function cloneOptional<T>(value: T | null | undefined): T | undefined {
  return value == null ? undefined : cloneJson(value)
}

function getCopyName(name: string, existingNames: string[]): string {
  const names = new Set(existingNames)
  const baseName = `${name}（副本）`
  if (!names.has(baseName)) return baseName
  let idx = 2
  while (names.has(`${name}（副本${idx}）`)) idx += 1
  return `${name}（副本${idx}）`
}

function cleanCopiedSubsystems(subsystems: Subsystem[] | null | undefined): Subsystem[] {
  return cloneJson(subsystems ?? []).map((subsystem) => {
    delete subsystem.id
    delete subsystem.scheme_id
    subsystem.combos = (subsystem.combos ?? []).map((combo) => {
      delete combo.id
      return combo
    })
    subsystem.tower_groups = (subsystem.tower_groups ?? []).map((group) => {
      delete group.id
      return group
    })
    return subsystem
  })
}

async function copyScheme(row: { id: string; name: string }, event?: MouseEvent) {
  event?.stopPropagation()
  if (store.items.length >= 5) {
    ElMessage.warning(t('scheme.maxReached'))
    return
  }
  if (copyingSchemes.value.has(row.id)) return

  copyingSchemes.value.add(row.id)
  try {
    const { data: source } = await getScheme(row.id)
    const payload: SystemSchemeCreate = {
      name: getCopyName(source.name, store.items.map((item) => item.name)),
      building_id: source.building_id,
      scheme_index: store.items.length + 1,
      safety_margin: source.safety_margin,
      control_strategy: cloneOptional(source.control_strategy),
      diagram_json: cloneOptional(source.diagram_json),
      subsystems: cleanCopiedSubsystems(source.subsystems),
    }
    await store.add(projectId.value, payload)
    ElMessage.success('方案已复制')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  } finally {
    copyingSchemes.value.delete(row.id)
  }
}

// ------- 删除 -------
async function removeOne(id: string, name: string) {
  try {
    await ElMessageBox.confirm(t('scheme.deleteConfirmOne', { name }), t('common.warning'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  await store.remove(projectId.value, id)
  ElMessage.success(t('common.deleted'))
}

// ------- 编辑（名称 + 安全裕量） -------
function openEditDialog(row: { id: string; name: string; safety_margin?: number | null }, event?: MouseEvent) {
  event?.stopPropagation()
  editForm.id = row.id
  editForm.name = row.name
  editForm.safety_margin = Number(row.safety_margin ?? 1.0)
  editDialogVisible.value = true
}

async function confirmEdit() {
  const name = editForm.name.trim()
  if (!name) {
    ElMessage.warning(t('scheme.namePlaceholder'))
    return
  }
  try {
    await updateScheme(editForm.id, {
      name,
      safety_margin: Number(editForm.safety_margin ?? 1.0),
    })
    editDialogVisible.value = false
    await store.fetchList(projectId.value)
    ElMessage.success(t('common.updated') || '已更新')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  }
}

// ------- 导航 -------
function openScheme(id: string) {
  router.push(`/projects/${projectId.value}/system-schemes/${id}`)
}

// ------- 能耗仿真（占位）-------
const runningIds = ref<Set<string>>(new Set())
function runEnergySim(id: string) {
  ElMessage.info(t('scheme.energySimTba'))
  // Placeholder for future energy simulation API call:
  // await runEnergySimulation(id); refresh list.
  void id
}
function runAllEnergySim() {
  if (!store.items.length) return
  ElMessage.info(t('scheme.energySimTba'))
}

// ------- 工具 -------
function formatNum(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  return v >= 1000 ? v.toFixed(0) : v.toFixed(1)
}
function coolingShort(item: { cooling_load_peak: number | null; cooling_capacity_total: number }) {
  return (
    item.cooling_load_peak !== null &&
    item.cooling_load_peak > 0 &&
    item.cooling_capacity_total < item.cooling_load_peak
  )
}
function heatingShort(item: { heating_load_peak: number | null; heating_capacity_total: number }) {
  return (
    item.heating_load_peak !== null &&
    item.heating_load_peak > 0 &&
    item.heating_capacity_total < item.heating_load_peak
  )
}
function hasEnergyResult(item: {
  annual_energy_total: number | null
}): boolean {
  return item.annual_energy_total !== null && item.annual_energy_total !== undefined
}
function buildingLabel(row: { building_name: string | null; subsystem_count: number }): string {
  return `${row.building_name || '-'}（${row.subsystem_count}${t('scheme.subsystemUnit')}）`
}
function splitAnnualEnergy(
  item: { annual_cooling_total: number | null; annual_heating_total: number | null; annual_energy_total: number | null },
  kind: 'cooling' | 'heating',
): number | null {
  if (item.annual_energy_total === null || item.annual_energy_total === undefined) return null
  const cooling = Number(item.annual_cooling_total ?? 0)
  const heating = Number(item.annual_heating_total ?? 0)
  const total = cooling + heating
  if (total <= 0) return null
  const share = kind === 'cooling' ? cooling / total : heating / total
  return item.annual_energy_total * share
}

watch(projectId, async () => {
  store.$reset()
  await Promise.all([store.fetchList(projectId.value), loadBuildings()])
})

onMounted(async () => {
  await Promise.all([store.fetchList(projectId.value), loadBuildings()])
})
</script>

<template>
  <div class="scheme-list-view">
    <!-- Section header -->
    <div v-if="!isMobile" class="section-header">
      <div class="section-header-left">
        <h2>{{ t('scheme.sectionTitle') }}</h2>
        <span class="section-hint">{{ t('scheme.sectionHint') }}</span>
      </div>
      <div class="section-header-right">
        <el-button
          :icon="StartSimulationIcon"
          :disabled="!store.items.length"
          @click="runAllEnergySim"
        >
          {{ t('scheme.runAllEnergy') }}
        </el-button>
        <el-button type="primary" :icon="AddWorkspaceItemIcon" @click="openNewDialog">
          {{ t('scheme.addNew') }}
        </el-button>
      </div>
    </div>

    <!-- Card grid -->
    <div v-loading="store.loadingList" class="scheme-grid">
      <div
        v-for="row in store.items"
        :key="row.id"
        class="scard"
        :class="{
          'scard--dim': !hasEnergyResult(row),
        }"
        @click="openScheme(row.id)"
      >
        <div class="scard-header">
          <div class="scard-title-mark">
            <el-icon><Tickets /></el-icon>
          </div>
          <div class="scard-title">
            <div class="scard-name-main">
              <span class="scard-name">{{ row.name }}</span>
              <span class="scard-building">{{ buildingLabel(row) }}</span>
            </div>
          </div>
          <div class="scard-card-actions" @click.stop>
            <el-button
              type="primary"
              :icon="CopyDocument"
              size="small"
              text
              :loading="copyingSchemes.has(row.id)"
              @click="copyScheme(row, $event)"
              title="复制方案"
            />
            <el-button
              type="primary"
              :icon="Edit"
              size="small"
              text
              @click="openEditDialog(row, $event)"
              :title="t('common.edit') || '编辑'"
            />
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              text
              @click.stop="removeOne(row.id, row.name)"
              :title="t('common.delete')"
            />
          </div>
        </div>

        <div class="scard-metric-panels">
          <div class="metric-panel metric-panel--cool" :class="{ 'metric-panel--short': coolingShort(row) }">
            <div class="metric-panel-title">
              <span class="metric-panel-symbol metric-panel-symbol--snow" aria-hidden="true">❄</span>
              <span>制冷</span>
            </div>
            <div class="metric-row"><span>峰值负荷</span><strong>{{ formatNum(row.cooling_load_peak) }} <em>kW</em></strong></div>
            <div class="metric-row"><span>装机容量</span><strong>{{ formatNum(row.cooling_capacity_total) }} <em>kW</em></strong></div>
            <div class="metric-row"><span>累计制冷量</span><strong>{{ formatNum(row.annual_cooling_total) }} <em>kWh</em></strong></div>
            <div class="metric-row"><span>耗电量</span><strong>{{ formatNum(splitAnnualEnergy(row, 'cooling')) }} <em>kWh</em></strong></div>
          </div>
          <div class="metric-panel metric-panel--heat" :class="{ 'metric-panel--short': heatingShort(row) }">
            <div class="metric-panel-title">
              <span class="metric-panel-symbol"><el-icon><Sunny /></el-icon></span>
              <span>制热</span>
            </div>
            <div class="metric-row"><span>峰值负荷</span><strong>{{ formatNum(row.heating_load_peak) }} <em>kW</em></strong></div>
            <div class="metric-row"><span>装机容量</span><strong>{{ formatNum(row.heating_capacity_total) }} <em>kW</em></strong></div>
            <div class="metric-row"><span>累计制热量</span><strong>{{ formatNum(row.annual_heating_total) }} <em>kWh</em></strong></div>
            <div class="metric-row"><span>耗电量</span><strong>{{ formatNum(splitAnnualEnergy(row, 'heating')) }} <em>kWh</em></strong></div>
          </div>
        </div>

        <div v-if="!isMobile" class="scard-actions" @click.stop>
          <el-button
            size="small"
            :icon="StartSimulationIcon"
            :loading="runningIds.has(row.id)"
            @click.stop="runEnergySim(row.id)"
          >
            {{ t('scheme.runEnergy') }}
          </el-button>
          <el-button type="primary" size="small" @click.stop="openScheme(row.id)">
            {{ t('scheme.openDetail') }}
          </el-button>
        </div>
      </div>
    </div>

    <el-empty
      v-if="!store.loadingList && !store.items.length"
      :description="t('scheme.noSchemeYet')"
    >
      <el-button type="primary" :icon="AddWorkspaceItemIcon" @click="openNewDialog">
        {{ t('scheme.addNew') }}
      </el-button>
    </el-empty>

    <Teleport to="body">
      <!-- 移动端底部固定主操作栏 -->
      <div v-if="isMobile" class="mobile-action-bar">
        <el-button
          class="mab-btn mab-btn--simulate"
          :disabled="!store.items.length"
          @click="runAllEnergySim"
        >
          <span class="mab-icon" aria-hidden="true">
            <el-icon><StartSimulationIcon /></el-icon>
          </span>
          <span class="mab-title">仿真</span>
        </el-button>
        <el-button
          class="mab-btn mab-btn--create"
          @click="openNewDialog"
        >
          <span class="mab-icon" aria-hidden="true">
            <el-icon><AddWorkspaceItemIcon /></el-icon>
          </span>
          <span class="mab-title">新增</span>
        </el-button>
      </div>
    </Teleport>

    <!-- 新建对话框 -->
    <el-dialog v-model="newDialogVisible" :title="t('scheme.addNew')" width="480px" append-to-body>
      <el-form label-width="120px">
        <el-form-item :label="t('scheme.name')" required>
          <el-input v-model="newForm.name" :placeholder="t('scheme.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('scheme.bindBuilding')" required>
          <el-select
            v-model="newForm.building_id"
            :loading="loadingBuildings"
            :placeholder="t('scheme.selectBuilding')"
            style="width: 100%"
          >
            <el-option
              v-for="b in buildingsWithLoad"
              :key="b.id"
              :label="b.name"
              :value="b.id"
            />
          </el-select>
          <div class="form-tip">{{ t('scheme.bindBuildingTip') }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmNew">{{ t('common.create') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑方案" width="420px" append-to-body>
      <el-form label-width="96px">
        <el-form-item :label="t('scheme.name')" required>
          <el-input v-model="editForm.name" :placeholder="t('scheme.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('scheme.strategy.safetyMargin')" required>
          <el-input-number
            v-model="editForm.safety_margin"
            :min="0"
            :max="1.2"
            :step="0.01"
            :precision="2"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmEdit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.scheme-list-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ----------------- Section Header ----------------- */
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

/* ----------------- Card Grid ----------------- */
.scheme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr));
  gap: 16px;
  min-width: 0;
}

.scard {
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
.scard:hover {
  transform: var(--sim-card-hover-transform);
  box-shadow: var(--sim-card-hover-shadow);
  border-color: var(--sim-card-hover-border);
}
.scard--dim .metric-panel {
  background: var(--sim-metric-dim-bg);
  opacity: 0.78;
}
.scard--dim .metric-row strong {
  color: var(--sim-metric-dim-value);
}

.scard-header {
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
}
.scard-title-mark {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: #0f766e;
  background: linear-gradient(135deg, #ecfdf5, #f0fdfa);
  font-size: 22px;
}
.scard-title {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  flex: 1 1 0;
  overflow: hidden;
}
.scard-name-main {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
  width: 100%;
  overflow: hidden;
}
.scard-name {
  display: block;
  font-size: 16px;
  font-weight: var(--font-weight-regular);
  color: var(--sim-card-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  max-width: 100%;
}
.scard-building {
  display: block;
  font-size: 12px;
  color: var(--sim-card-subtitle);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.scard-card-actions {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  margin-left: auto;
}
.scard-card-actions :deep(.el-button) {
  width: 34px;
  height: 34px;
  padding: 0;
  font-size: 18px;
}
.scard-card-actions :deep(.el-button + .el-button) {
  margin-left: 2px;
}
/* kept for compatibility with older hot-reloaded DOM */
.scard-rename {
  flex-shrink: 0;
  margin-left: -4px;
  opacity: 0.55;
  transition: opacity 0.15s;
}
.scard-rename:hover { opacity: 1; }
.scard:hover .scard-rename { opacity: 1; }
.scard-name-row > .scard-rename + * { margin-left: auto; }
.tag-text {
  margin-left: 2px;
  white-space: nowrap;
}

.scard-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border-radius: 8px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #475569;
  line-height: 1.2;
}
.meta-pill-icon {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  color: #0891b2;
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

/* ----------------- Metric Panels ----------------- */
.scard-metric-panels {
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
.metric-panel--short {
  border-color: var(--sim-metric-short-border);
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

/* ----------------- Actions ----------------- */
.scard-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 4px;
}

.form-tip {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}

/* ----------------- Mobile ----------------- */
@media (max-width: 768px) {
  .scheme-list-view { gap: 12px; padding: 0 12px 12px; }
  .scheme-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
    min-width: 0;
  }
  .scard {
    min-width: 0;
    padding: var(--sim-card-mobile-padding);
    gap: var(--sim-card-mobile-gap);
    border-radius: var(--sim-card-radius);
    overflow: hidden;
    background: var(--sim-card-bg);
    border-color: var(--sim-card-border);
    box-shadow: var(--sim-card-shadow);
  }
  .scard-header { gap: 12px; }
  .scard-title-mark { width: 38px; height: 38px; font-size: 20px; }
  .scard-name { font-size: 16px; }
  .scard-card-actions { margin-left: 4px; }
  .scard-metric-panels { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
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
}
</style>
