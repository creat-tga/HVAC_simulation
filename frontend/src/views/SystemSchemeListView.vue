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
  Plus,
  Delete,
  VideoPlay,
  OfficeBuilding,
  Setting,
  Edit,
} from '@element-plus/icons-vue'
import { useSystemSchemeStore } from '@/stores/system-scheme'
import { useProjectStore } from '@/stores/project'
import { useResponsive } from '@/composables/useResponsive'
import { getSimulations } from '@/api/simulation'
import { updateScheme } from '@/api/system-scheme'
import type { SystemSchemeCreate } from '@/types/system-scheme'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useSystemSchemeStore()
const projectStore = useProjectStore()
const { isMobile } = useResponsive()

const projectId = computed(() => route.params.projectId as string)

// ------- 建筑候选（仅展示已完成负荷仿真的建筑作为可绑定项）-------
interface BuildingOpt {
  id: string
  name: string
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
        opts.push({ id: b.id, name: b.name, hasLoad: done.length > 0 })
      } catch {
        opts.push({ id: b.id, name: b.name, hasLoad: false })
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
function formatCop(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  return v.toFixed(2)
}
function formatSafetyMargin(v: number | null | undefined): string {
  return Number(v ?? 1.0).toFixed(2)
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
          :icon="VideoPlay"
          :disabled="!store.items.length"
          @click="runAllEnergySim"
        >
          {{ t('scheme.runAllEnergy') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openNewDialog">
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
          <div class="scard-title">
            <div class="scard-name-row">
              <div class="scard-name-main">
                <span class="scard-name">{{ row.name }}</span>
                <el-tag
                  v-if="!isMobile"
                  :type="hasEnergyResult(row) ? 'success' : 'info'"
                  size="small"
                  effect="light"
                >
                  {{ hasEnergyResult(row) ? t('scheme.hasEnergyResult') : t('scheme.noEnergyResult') }}
                </el-tag>
              </div>
              <div class="scard-card-actions" @click.stop>
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
            <div class="scard-meta">
              <span class="meta-pill meta-pill--bldg">
                <el-icon class="meta-pill-icon"><OfficeBuilding /></el-icon>
                <span class="meta-pill-value">{{ row.building_name || '-' }}</span>
              </span>
              <span class="meta-pill">
                <el-icon class="meta-pill-icon"><Setting /></el-icon>
                <span class="meta-pill-value">{{ row.subsystem_count }}</span>
                <span class="meta-pill-unit">{{ t('scheme.subsystemUnit') }}</span>
              </span>
              <span class="meta-pill meta-pill--safety" @click.stop>
                <span class="meta-pill-unit">{{ t('scheme.strategy.safetyMargin') }}</span>
                <span class="meta-pill-value">{{ formatSafetyMargin(row.safety_margin) }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="scard-stats">
          <!-- 1. 冷负荷峰值 -->
          <div class="stat-item stat-cool">
            <span class="stat-tag stat-tag--cool">制<wbr />冷</span>
            <span class="stat-name">负荷<wbr />峰值</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.cooling_load_peak) }}</span>
              <span class="stat-unit">kW</span>
            </div>
          </div>
          <!-- 2. 热负荷峰值 -->
          <div class="stat-item stat-heat">
            <span class="stat-tag stat-tag--heat">制<wbr />热</span>
            <span class="stat-name">负荷<wbr />峰值</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.heating_load_peak) }}</span>
              <span class="stat-unit">kW</span>
            </div>
          </div>
          <!-- 3. 装机容量（制冷） -->
          <div
            class="stat-item stat-cool-soft"
            :class="{ 'stat-short': coolingShort(row) }"
          >
            <span class="stat-tag stat-tag--cool">制<wbr />冷</span>
            <span class="stat-name">装机<wbr />容量</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.cooling_capacity_total) }}</span>
              <span class="stat-unit">kW</span>
            </div>
          </div>
          <!-- 4. 装机容量（制热） -->
          <div
            class="stat-item stat-heat-soft"
            :class="{ 'stat-short': heatingShort(row) }"
          >
            <span class="stat-tag stat-tag--heat">制<wbr />热</span>
            <span class="stat-name">装机<wbr />容量</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.heating_capacity_total) }}</span>
              <span class="stat-unit">kW</span>
            </div>
          </div>
          <!-- 5. 累计制冷量 -->
          <div class="stat-item stat-energy">
            <span class="stat-tag stat-tag--cool">制<wbr />冷</span>
            <span class="stat-name">年<wbr />累计</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.annual_cooling_total) }}</span>
              <span class="stat-unit">kWh</span>
            </div>
          </div>
          <!-- 6. 累计制热量 -->
          <div class="stat-item stat-energy">
            <span class="stat-tag stat-tag--heat">制<wbr />热</span>
            <span class="stat-name">年<wbr />累计</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.annual_heating_total) }}</span>
              <span class="stat-unit">kWh</span>
            </div>
          </div>
          <!-- 7. 系统能耗 -->
          <div class="stat-item stat-energy">
            <span class="stat-tag stat-tag--sys">系<wbr />统</span>
            <span class="stat-name">年<wbr />能耗</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatNum(row.annual_energy_total) }}</span>
              <span class="stat-unit">kWh</span>
            </div>
          </div>
          <!-- 8. 系统能效 -->
          <div class="stat-item stat-cop">
            <span class="stat-tag stat-tag--sys">系<wbr />统</span>
            <span class="stat-name">能效<wbr />比</span>
            <div class="stat-value">
              <span class="stat-num">{{ formatCop(row.system_cop) }}</span>
            </div>
          </div>
        </div>

        <div v-if="!isMobile" class="scard-actions" @click.stop>
          <el-button
            size="small"
            :icon="VideoPlay"
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
      <el-button type="primary" :icon="Plus" @click="openNewDialog">
        {{ t('scheme.addNew') }}
      </el-button>
    </el-empty>

    <!-- 移动端底部固定主操作栏 -->
    <div v-if="isMobile" class="mobile-action-bar">
      <el-button
        class="mab-btn"
        :icon="VideoPlay"
        :disabled="!store.items.length"
        @click="runAllEnergySim"
      >
        {{ t('scheme.runAllEnergy') }}
      </el-button>
      <el-button
        class="mab-btn"
        type="primary"
        :icon="Plus"
        @click="openNewDialog"
      >
        {{ t('scheme.addNew') }}
      </el-button>
    </div>

    <!-- 新建对话框 -->
    <el-dialog v-model="newDialogVisible" :title="t('scheme.addNew')" width="480px">
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

    <el-dialog v-model="editDialogVisible" title="编辑方案" width="420px">
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
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 16px;
}

.scard {
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
.scard:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 36px rgba(8, 145, 178, 0.14), 0 4px 10px rgba(15, 23, 42, 0.06);
  border-color: rgba(8, 145, 178, 0.45);
}
.scard--dim .scard-stats .stat-item {
  background: #f8fafc !important;
  border-color: #e5e7eb !important;
  opacity: 0.72;
}
.scard--dim .scard-stats .stat-item .stat-unit {
  visibility: hidden;
}
.scard--dim .scard-stats .stat-item .stat-value {
  color: #94a3b8;
}

.scard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}
.scard-title {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  width: 100%;
}
.scard-name-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.scard-name-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.scard-name {
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.scard-card-actions {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
}
.scard-card-actions :deep(.el-button) {
  padding: 4px;
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
  padding: 4px 11px;
  border-radius: 999px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #475569;
  line-height: 1.2;
}
.meta-pill--bldg {
  background: linear-gradient(135deg, #ecfeff, #f0f9ff);
  border-color: rgba(8, 145, 178, 0.22);
  color: #0e7490;
}
.meta-pill--safety {
  border-radius: 999px;
  padding: 4px 10px;
  background: #f8fafc;
}
.meta-pill--safety :deep(.el-input-number) {
  width: 92px;
}
.meta-pill--safety :deep(.el-input__wrapper) {
  padding-left: 6px;
  padding-right: 6px;
}
.meta-pill--safety :deep(.el-input__inner) {
  text-align: center;
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

/* ----------------- Stats grid -----------------
   每个 stat-item 拆为 [tag][name][value] 三行；
   父级 grid 用固定行高让相邻 item 的对应行严格横向对齐；
   tag/name 用 <wbr/> 控制只在两字处断行（不会出现"负荷峰\n值"）。 */
.scard-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px 8px;
  align-items: stretch;
}
.stat-item {
  display: grid;
  /* 固定行高确保跨 item 横向对齐：tag 行 22 / name 行 36（两行） / value 行 22 */
  grid-template-rows: 22px 36px 22px;
  row-gap: 2px;
  padding: 8px 6px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  min-width: 0;
  text-align: center;
  /* 关闭字符级断行；仅在 <wbr/> 处可断 */
  word-break: keep-all;
  overflow-wrap: normal;
}
.stat-tag {
  align-self: center;
  justify-self: center;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  line-height: 1.1;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #475569;
  white-space: normal;
  max-width: 100%;
  text-align: center;
}
.stat-tag--cool { background: rgba(59, 130, 246, 0.12); color: #1d4ed8; }
.stat-tag--heat { background: rgba(249, 115, 22, 0.12); color: #c2410c; }
.stat-tag--sys  { background: rgba(99, 102, 241, 0.12); color: #4f46e5; }
.stat-name {
  align-self: center;
  font-size: 12px;
  color: #64748b;
  line-height: 1.2;
  white-space: normal;
  /* 最多 2 行（行高 14.4 × 2 ≈ 29，留 36 容错） */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-align: center;
}
.stat-value {
  align-self: center;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
  white-space: nowrap;
  min-width: 0;
  line-height: 1.1;
}
.stat-num { overflow: hidden; text-overflow: ellipsis; }
.stat-unit {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  margin-left: 2px;
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
.stat-energy {
  background: linear-gradient(135deg, #f5f3ff 0%, #faf5ff 100%);
}
.stat-cop {
  background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
}
.stat-short {
  border-color: #fca5a5;
  background: #fef2f2;
}
.stat-short .stat-value {
  color: #dc2626;
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
  .scheme-list-view { gap: 12px; padding-bottom: 84px; }
  .scheme-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .scard { padding: 14px; gap: 10px; }
  .scard-name { font-size: 16px; }
  .scard-name-main {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .scard-card-actions { margin-left: 4px; }
  .scard-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 8px; }
  .stat-item { padding: 6px 4px; }
  .stat-tag { font-size: 10.5px; padding: 1px 5px; }
  .stat-name { font-size: 11px; }
  .stat-value { font-size: 14px; }
  .mobile-action-bar {
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: calc(64px + env(safe-area-inset-bottom, 0px));
    display: flex;
    gap: 10px;
    z-index: 90;
    pointer-events: none;
  }
  .mobile-action-bar .mab-btn {
    flex: 1;
    pointer-events: auto;
    height: 48px;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
  }
}
</style>
