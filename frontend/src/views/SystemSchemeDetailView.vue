<script setup lang="ts">
/**
 * SystemSchemeDetailView — 单个方案详情页（顶层 3 步骤 + 设备选型下多 Subsystem Tab）.
 *
 * 顶部 hero：4 项指标 + 操作按钮（保存 / 校验 / 返回 / 下一步）
 * 中部：el-steps（设备选型 / 控制策略 / 系统图） + el-radio-group 切换
 * 设备选型 step：subsystem Tab（可新增多个，类型选择 chiller_plant/air_cooled/shared_tower）
 */

import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Check, Setting, Delete } from '@element-plus/icons-vue'
import { useSystemSchemeStore } from '@/stores/system-scheme'
import SubsystemEditor from '@/components/scheme/SubsystemEditor.vue'
import type {
  Subsystem,
  SubsystemType,
  SystemSchemeUpdate,
} from '@/types/system-scheme'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useSystemSchemeStore()

const projectId = computed(() => route.params.projectId as string)
const schemeId = computed(() => route.params.schemeId as string)

// 校验问题：存在 error 时仅展示 error；error 全部修复后再展示 warning
const visibleIssues = computed(() => {
  const all = store.validation?.issues || []
  const errors = all.filter((i) => i.severity === 'error')
  return errors.length ? errors : all
})

const wizardStep = ref<'selection' | 'strategy' | 'diagram'>('selection')
const STEPS = [
  { key: 'selection' as const, titleKey: 'scheme.steps.selection', subKey: 'scheme.steps.selectionDesc' },
  { key: 'strategy' as const, titleKey: 'scheme.steps.strategy', subKey: 'scheme.steps.tba' },
  { key: 'diagram' as const, titleKey: 'scheme.steps.diagram', subKey: 'scheme.steps.tba' },
]
const stepIdx = computed(() => STEPS.findIndex((s) => s.key === wizardStep.value))
function gotoStep(key: 'selection' | 'strategy' | 'diagram') {
  wizardStep.value = key
}

const activeSubIdx = ref(0)

// Local mutable model bound to store.activeScheme; mark dirty on change
const local = reactive<{
  name: string
  safety_margin: number
  subsystems: Subsystem[]
}>({ name: '', safety_margin: 1.0, subsystems: [] })

// Internal flags used by syncFromStore + the local watcher to avoid the
// "saved but still dirty" loop. Declared up front so syncFromStore can
// reference suppressDirty without TDZ issues.
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
let autoSaving = false
let suppressDirty = false

function syncFromStore() {
  const s = store.activeScheme
  if (!s) return
  // Suppress the deep watch on `local` while we replay store data into the
  // local reactive copy, so we don't mistakenly mark dirty again right after
  // a successful save (the assignments below would otherwise trigger the
  // watcher and call markDirty()).
  suppressDirty = true
  local.name = s.name
  local.safety_margin = s.safety_margin
  local.subsystems = JSON.parse(JSON.stringify(s.subsystems || [])) as Subsystem[]
  if (activeSubIdx.value >= local.subsystems.length) activeSubIdx.value = 0
  void nextTick(() => {
    suppressDirty = false
    // Force-clear in case the watcher already queued a markDirty earlier.
    store.dirty = false
  })
}

watch(() => store.activeScheme?.id, syncFromStore)

function onNameBlur() {
  if (!local.name.trim()) {
    local.name = store.activeScheme?.name?.trim() || `${t('scheme.namePlaceholder')}`
  }
}

// ---- 自动保存 + 实时刷新派生数据（debounce 700ms） ----
watch(
  () => [local.name, local.safety_margin, local.subsystems] as const,
  () => {
    if (!store.activeScheme) return
    if (suppressDirty || autoSaving) return
    store.markDirty()
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    autoSaveTimer = setTimeout(async () => {
      if (!local.name.trim()) return
      autoSaving = true
      try {
        // Pre-validate: skip the actual save when errors exist; keep the
        // unsaved changes so user can fix the highlighted problems. We still
        // refresh `validation` so alerts update in real time.
        const payload = buildPayload()
        const pre = await store.validatePayload(schemeId.value, payload)
        const hasError = pre.issues.some((i) => i.severity === 'error')
        if (hasError) return
        await store.save(schemeId.value, payload)
        syncFromStore()
        // 自动保存后同步刷新校验，避免就地高亮因 ID 失配而消失
        await store.validateActive(schemeId.value)
      } catch {
        // ignore auto-save errors silently
      } finally {
        autoSaving = false
      }
    }, 700)
  },
  { deep: true },
)

// ----- Subsystem add/remove + selection -----
const MAX_SUBSYSTEMS = 5
const addSubDialogVisible = ref(false)
const newSubType = ref<SubsystemType>('chiller_plant')
const newSubName = ref('')

const selectMode = ref(false)
const selectedIdx = ref<Set<number>>(new Set())

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIdx.value = new Set()
}
function toggleSelect(idx: number) {
  const s = new Set(selectedIdx.value)
  if (s.has(idx)) s.delete(idx)
  else s.add(idx)
  selectedIdx.value = s
}
function selectAll() {
  selectedIdx.value = new Set(local.subsystems.map((_, i) => i))
}
function selectNone() {
  selectedIdx.value = new Set()
}

function openAddSub() {
  if (local.subsystems.length >= MAX_SUBSYSTEMS) {
    ElMessage.warning(t('scheme.maxSubsystems'))
    return
  }
  newSubType.value = 'chiller_plant'
  newSubName.value = ''
  addSubDialogVisible.value = true
}

function defaultDesignParams(typ: SubsystemType): Record<string, unknown> {
  if (typ === 'chiller_plant') {
    return {
      chw_supply_temp: 7, chw_delta_temp: 5, chw_pump_head: 35,
      header_pressure_drop: 21, cw_supply_temp: 30, cw_delta_temp: 5, cw_pump_head: 30,
    }
  }
  if (typ === 'air_cooled') {
    return {
      cooling_supply_temp: 7, cooling_delta_temp: 5,
      heating_supply_temp: 45, heating_delta_temp: 5,
      pipe_system: 'two_pipe', pump_head: 35, header_pressure_drop: 21,
      chw_pump_head: 35, chw_header_pressure_drop: 21,
      hw_pump_head: 35, hw_header_pressure_drop: 21,
    }
  }
  return {}
}

function confirmAddSub() {
  const idx = local.subsystems.length + 1
  const name = newSubName.value.trim() || `${t('scheme.types.' + newSubType.value)} ${idx}`
  local.subsystems.push({
    // Pre-assign a stable id so dry-run /validate-payload can echo
    // subsystem_id back and ComboEditor / TowerGroupEditor can match
    // issues to this subsystem before the first save round-trip.
    id: crypto.randomUUID(),
    subsystem_index: idx,
    subsystem_type: newSubType.value,
    name,
    design_params: defaultDesignParams(newSubType.value),
    combos: [],
    tower_groups: newSubType.value === 'chiller_plant'
      ? [{ id: crypto.randomUUID(), group_index: 1, tower_model_id: null, count: 1, factor: 0.85 }]
      : [],
  })
  activeSubIdx.value = local.subsystems.length - 1
  addSubDialogVisible.value = false
}

async function removeSub(idx: number) {
  if (local.subsystems.length <= 1) {
    ElMessage.warning(t('scheme.minSubsystemRequired'))
    return
  }
  const sub = local.subsystems[idx]
  try {
    await ElMessageBox.confirm(
      t('scheme.deleteSubsystemConfirm', { name: sub.name }),
      t('common.warning'),
      { type: 'warning', confirmButtonText: t('common.delete'), cancelButtonText: t('common.cancel') },
    )
  } catch { return }
  local.subsystems.splice(idx, 1)
  // re-index for display only (subsystem_index can stay; UI uses array idx)
  if (activeSubIdx.value >= local.subsystems.length) activeSubIdx.value = Math.max(0, local.subsystems.length - 1)
}

async function removeSelected() {
  if (!selectedIdx.value.size) {
    ElMessage.warning(t('scheme.pickAtLeastOneSub'))
    return
  }
  if (local.subsystems.length - selectedIdx.value.size < 1) {
    ElMessage.warning(t('scheme.minSubsystemRequired'))
    return
  }
  try {
    await ElMessageBox.confirm(
      t('scheme.deleteSubsystemBatchConfirm', { n: selectedIdx.value.size }),
      t('common.warning'),
      { type: 'warning', confirmButtonText: t('common.delete'), cancelButtonText: t('common.cancel') },
    )
  } catch { return }
  const sortedDesc = [...selectedIdx.value].sort((a, b) => b - a)
  for (const i of sortedDesc) local.subsystems.splice(i, 1)
  selectedIdx.value = new Set()
  selectMode.value = false
  activeSubIdx.value = 0
  ElMessage.success(t('common.deleted'))
}

// ----- save -----
const saving = ref(false)

function buildPayload(): SystemSchemeUpdate {
  return {
    name: local.name,
    safety_margin: local.safety_margin,
    subsystems: local.subsystems,
  }
}

/**
 * Scroll to the first issue in a validation report. Errors take precedence;
 * if only warnings exist, the first warning alert is highlighted instead.
 * Also switches the active subsystem tab so the issue is visible.
 */
function locateFirstIssue(rep: { issues: Array<{ severity: string; subsystem_id?: string | null }> }) {
  if (!rep.issues.length) return
  const errors = rep.issues.filter((i) => i.severity === 'error')
  const first = errors[0] || rep.issues[0]
  if (first.subsystem_id) {
    const tabIdx = local.subsystems.findIndex((s) => s.id === first.subsystem_id)
    if (tabIdx >= 0) activeSubIdx.value = tabIdx
  }
  setTimeout(() => {
    let target: Element | null = null
    if (errors.length) {
      // Priority: per-row red highlight > orphan subsystem-level error block
      // > any error alert anywhere on the page.
      target = document.querySelector('.combo-block.has-error, .tower-row.has-error')
        || document.querySelector('.subsystem-issues.has-error')
        || document.querySelector('.el-alert--error')
    } else {
      target = document.querySelector('.el-alert--warning')
    }
    if (target) (target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 200)
}

async function save() {
  if (!local.name.trim()) {
    ElMessage.warning(t('scheme.namePlaceholder'))
    return
  }
  saving.value = true
  try {
    // 1) Dry-run validate the unsaved payload first. If any errors exist,
    //    refuse to save and locate the first one. Warnings do not block save.
    const payload = buildPayload()
    const pre = await store.validatePayload(schemeId.value, payload)
    const preErrors = pre.issues.filter((i) => i.severity === 'error')
    if (preErrors.length) {
      ElMessage.error(t('scheme.saveBlockedByErrors', { n: preErrors.length }))
      locateFirstIssue(pre)
      return
    }
    // 2) Persist + refresh derived/summary, then run server validation again
    //    on the saved scheme so highlights stay accurate.
    await store.save(schemeId.value, payload)
    syncFromStore()
    const rep = await store.validateActive(schemeId.value)
    ElMessage.success(t('common.saved'))
    if (rep.issues.length) {
      const warns = rep.issues.filter((i) => i.severity === 'warning')
      if (warns.length) {
        // Save succeeded but there are warnings to review.
        ElMessage.warning(t('scheme.savedWithWarnings', { n: warns.length }))
      }
      locateFirstIssue(rep)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('common.error'))
  } finally {
    saving.value = false
  }
}

function goBackToList() {
  router.push(`/projects/${projectId.value}/system-schemes`)
}

// ----- 离开提醒 -----
function beforeUnload(e: BeforeUnloadEvent) {
  if (store.dirty) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onBeforeRouteLeave(async (_to, _from, next) => {
  if (!store.dirty) return next()
  try {
    await ElMessageBox.confirm(
      t('scheme.leaveWarning'),
      t('common.warning'),
      { type: 'warning', confirmButtonText: t('common.leave'), cancelButtonText: t('common.stay') },
    )
    next()
  } catch {
    next(false)
  }
})

onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  // 让滚动只发生在 ssd-body 内：限制父容器 .ws-content 不滚动
  const wsContent = document.querySelector('.ws-content') as HTMLElement | null
  if (wsContent) {
    wsContent.dataset.prevOverflow = wsContent.style.overflow
    wsContent.style.overflow = 'hidden'
  }
  await store.fetchDetail(schemeId.value)
  syncFromStore()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnload)
  const wsContent = document.querySelector('.ws-content') as HTMLElement | null
  if (wsContent) {
    wsContent.style.overflow = wsContent.dataset.prevOverflow || ''
    delete wsContent.dataset.prevOverflow
  }
})

const coolingShort = computed(() => store.coolingShort)
const heatingShort = computed(() => store.heatingShort)

const capacityShortMessage = computed(() => {
  const parts: string[] = []
  if (coolingShort.value) parts.push(t('scheme.summary.coolingShortLabel'))
  if (heatingShort.value) parts.push(t('scheme.summary.heatingShortLabel'))
  if (!parts.length) return ''
  return t('scheme.summary.capacityShortDetailed', { kinds: parts.join('、') })
})
</script>

<template>
  <div v-loading="store.loadingDetail" class="ssd-page">
    <!-- ============== TOP BAR (single row: back + name + steps + save) ============== -->
    <div class="ssd-topbar">
      <el-button link :icon="ArrowLeft" @click="goBackToList" class="topbar-back">
        {{ t('scheme.backToList') }}
      </el-button>
      <el-divider direction="vertical" />
      <el-input
        v-model="local.name"
        class="topbar-name"
        :class="{ 'is-empty-error': !local.name.trim() }"
        :placeholder="t('scheme.namePlaceholder')"
        size="default"
        @blur="onNameBlur"
      />
      <div class="topbar-steps">
        <div
          v-for="(s, i) in STEPS"
          :key="s.key"
          class="stepitem"
          :class="{
            active: wizardStep === s.key,
            done: stepIdx > i,
            pending: stepIdx < i,
          }"
          @click="gotoStep(s.key)"
        >
          <div class="step-circle">
            <span v-if="stepIdx > i">✓</span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <div class="step-title">{{ t(s.titleKey) }}</div>
        </div>
      </div>
      <el-badge is-dot :hidden="!store.dirty" type="danger" class="topbar-save">
        <el-button type="primary" :icon="Check" :loading="saving" @click="save" size="default">
          {{ t('common.save') }}
        </el-button>
      </el-badge>
    </div>

    <!-- ============== STEP BODY ============== -->
    <el-card class="ssd-body" shadow="never">
      <el-form label-position="top" :inline="false" @submit.prevent>
      <template v-if="wizardStep === 'selection'">
        <!-- KPI: 冷热负荷 vs 装机容量（紧凑单行展示） -->
        <div class="sel-kpi">
          <div class="sel-kpi-group" :class="{ 'sel-kpi--short': coolingShort }">
            <span class="sel-kpi-tag sel-kpi-tag--cool">{{ t('scheme.summary.cooling') || '制冷' }}</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label">{{ t('scheme.summary.loadPeakShort') || '负荷峰值' }}</span>
              <span class="sel-kpi-val">{{ store.summary?.cooling_load_peak !== null && store.summary?.cooling_load_peak !== undefined ? store.summary.cooling_load_peak.toFixed(1) : '-' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
            <span class="sel-kpi-sep">/</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label">{{ t('scheme.summary.installedShort') || '装机' }}</span>
              <span class="sel-kpi-val">{{ store.summary?.cooling_capacity_total?.toFixed(1) ?? '0.0' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
          </div>
          <div class="sel-kpi-group" :class="{ 'sel-kpi--short': heatingShort }">
            <span class="sel-kpi-tag sel-kpi-tag--heat">{{ t('scheme.summary.heating') || '制热' }}</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label">{{ t('scheme.summary.loadPeakShort') || '负荷峰值' }}</span>
              <span class="sel-kpi-val">{{ store.summary?.heating_load_peak !== null && store.summary?.heating_load_peak !== undefined ? store.summary.heating_load_peak.toFixed(1) : '-' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
            <span class="sel-kpi-sep">/</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label">{{ t('scheme.summary.installedShort') || '装机' }}</span>
              <span class="sel-kpi-val">{{ store.summary?.heating_capacity_total?.toFixed(1) ?? '0.0' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
          </div>
        </div>
        <el-alert
          v-if="store.capacityShort"
          type="warning"
          :closable="false"
          :title="capacityShortMessage"
          class="sel-cap-alert"
          show-icon
        />

        <!-- Subsystem toolbar -->
        <div class="sub-toolbar">
          <div class="sub-toolbar-left">
            <span class="sub-count">
              {{ t('scheme.subsystemCount', { n: local.subsystems.length }) }}
              <span class="sub-count-cap"> / {{ MAX_SUBSYSTEMS }}</span>
            </span>
            <el-tag v-if="selectMode && selectedIdx.size" type="warning" size="small">
              {{ t('scheme.selectedCount', { n: selectedIdx.size }) }}
            </el-tag>
          </div>
          <div class="sub-toolbar-right">
            <template v-if="selectMode">
              <el-button size="small" @click="selectAll">{{ t('scheme.selectAll') }}</el-button>
              <el-button size="small" @click="selectNone">{{ t('scheme.selectNone') }}</el-button>
              <el-button
                size="small"
                type="danger"
                :icon="Delete"
                :disabled="!selectedIdx.size"
                @click="removeSelected"
              >
                {{ t('scheme.batchDelete') }}
              </el-button>
              <el-button size="small" @click="toggleSelectMode">
                {{ t('scheme.selectModeOn') }}
              </el-button>
            </template>
            <template v-else>
              <el-button
                size="small"
                :icon="Setting"
                :disabled="local.subsystems.length === 0"
                @click="toggleSelectMode"
              >
                {{ t('scheme.selectMode') }}
              </el-button>
              <el-button
                size="small"
                type="primary"
                :icon="Plus"
                :disabled="local.subsystems.length >= MAX_SUBSYSTEMS"
                @click="openAddSub"
              >
                {{ t('scheme.addSubsystem') }}
              </el-button>
            </template>
          </div>
        </div>

        <div v-if="!local.subsystems.length" class="empty-sub">
          <el-empty :description="t('scheme.noSubsystem')">
            <el-button type="primary" :icon="Plus" @click="openAddSub">
              {{ t('scheme.addSubsystem') }}
            </el-button>
          </el-empty>
        </div>

        <!-- Vertical stack of subsystems -->
        <div v-else class="sub-stack">
          <div
            v-for="(sub, idx) in local.subsystems"
            :key="idx"
            class="sub-block"
            :class="{ 'sub-block--selected': selectMode && selectedIdx.has(idx) }"
          >
            <div class="sub-block-head">
              <div class="sub-block-head-left">
                <el-checkbox
                  v-if="selectMode"
                  :model-value="selectedIdx.has(idx)"
                  @change="toggleSelect(idx)"
                />
                <span class="sub-idx">#{{ idx + 1 }}</span>
                <el-input
                  v-model="sub.name"
                  size="small"
                  class="sub-name-input"
                  :placeholder="t('scheme.subNamePlaceholder')"
                />
                <el-tag size="small" type="info" effect="plain">
                  {{ t('scheme.types.' + sub.subsystem_type) }}
                </el-tag>
              </div>
              <div class="sub-block-head-right">
                <el-button
                  size="small"
                  type="danger"
                  text
                  :icon="Delete"
                  :disabled="local.subsystems.length <= 1"
                  @click="removeSub(idx)"
                >
                  {{ t('common.delete') }}
                </el-button>
              </div>
            </div>

            <SubsystemEditor
              v-model="local.subsystems[idx]"
              :derived="store.derived?.subsystems.find((d) => d.id === sub.id) || null"
              :issues="visibleIssues.filter((iss) => iss.subsystem_id === sub.id)"
            />
          </div>
        </div>

        <!-- 校验报告改为就地高亮，无需此处单独表格 -->
      </template>

      <template v-else-if="wizardStep === 'strategy'">
        <el-empty :image-size="120" :description="t('scheme.steps.strategyTba')">
          <el-button disabled>{{ t('scheme.steps.tba') }}</el-button>
        </el-empty>
      </template>

      <template v-else>
        <el-empty :image-size="120" :description="t('scheme.steps.diagramTba')">
          <el-button disabled>{{ t('scheme.steps.tba') }}</el-button>
        </el-empty>
      </template>
      </el-form>
    </el-card>

    <!-- Add Subsystem dialog -->
    <el-dialog v-model="addSubDialogVisible" :title="t('scheme.addSubsystem')" width="420px">
      <el-form label-width="100px">
        <el-form-item :label="t('scheme.subType')">
          <el-radio-group v-model="newSubType">
            <el-radio-button label="chiller_plant">{{ t('scheme.types.chiller_plant') }}</el-radio-button>
            <el-radio-button label="air_cooled">{{ t('scheme.types.air_cooled') }}</el-radio-button>
            <el-radio-button label="shared_tower">{{ t('scheme.types.shared_tower') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('scheme.subName')">
          <el-input v-model="newSubName" :placeholder="t('scheme.subNamePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addSubDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmAddSub">{{ t('common.create') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ssd-page {
  padding: 4px 6px;
  max-width: none;
  margin: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* ============== TOP BAR (single row) ============== */
.ssd-topbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 6px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  flex-wrap: nowrap;
  min-width: 0;
}
.topbar-back { flex-shrink: 0; }
.topbar-name {
  flex: 0 0 160px;
  width: 160px;
}
.topbar-name.is-empty-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f56c6c inset;
  background: #fef2f2;
}
.topbar-steps {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1 1 auto;
  justify-content: center;
  min-width: 0;
  overflow: hidden;
}
.topbar-save { flex-shrink: 0; margin-left: auto; }

.stepitem {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px 4px 4px;
  cursor: pointer;
  user-select: none;
  border-radius: 999px;
  transition: background 0.18s;
  flex-shrink: 0;
}
.stepitem:hover { background: #f1f5f9; }
.stepitem.active {
  background: linear-gradient(135deg, #ecfeff 0%, #f5f3ff 100%);
}
.step-circle {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  background: #f1f5f9;
  color: #94a3b8;
  border: 2px solid #e2e8f0;
  flex-shrink: 0;
  transition: all 0.18s;
}
.stepitem.active .step-circle {
  background: linear-gradient(135deg, #06b6d4, #8b5cf6);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 2px 6px rgba(139, 92, 246, 0.28);
}
.stepitem.done .step-circle {
  background: #10b981;
  color: #fff;
  border-color: transparent;
}
.step-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.2;
  white-space: nowrap;
}
.stepitem.pending .step-title {
  color: #64748b;
  font-weight: 500;
}
@media (max-width: 900px) {
  .topbar-steps .step-title { display: none; }
  .topbar-name { flex: 0 0 120px; width: 120px; }
}

.ssd-body {
  border: 1px solid #e2e8f0;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}
.ssd-body :deep(.el-card__body) {
  padding: 10px 12px;
}

/* Hide +/- on ALL el-input-number inside body (设计参数/组合/冷却塔) */
.ssd-body :deep(.el-input-number .el-input-number__decrease),
.ssd-body :deep(.el-input-number .el-input-number__increase) {
  display: none !important;
}
.ssd-body :deep(.el-input-number .el-input__wrapper) {
  padding-left: 11px;
  padding-right: 11px;
}
.ssd-body :deep(.el-input-number .el-input__inner) {
  text-align: left;
}

/* All el-input-number in body fill their column for cleaner alignment */
.ssd-body :deep(.el-input-number) {
  width: 100%;
}
.ssd-body :deep(.el-form-item__label) {
  font-size: 13px;
  color: #475569;
  font-weight: 500;
  padding-bottom: 4px !important;
  line-height: 1.3;
}
.ssd-body :deep(.el-form-item) {
  margin-bottom: 14px;
}

/* KPI inside selection step (compact single row) */
.sel-kpi {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.sel-kpi-group {
  flex: 1 1 320px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f0f9ff 0%, #f5f3ff 100%);
  border: 1px solid #e2e8f0;
  min-height: 36px;
}
.sel-kpi--short {
  border-color: #fcd34d;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
}
.sel-kpi-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}
.sel-kpi-tag--cool { background: linear-gradient(135deg, #06b6d4, #0ea5e9); }
.sel-kpi-tag--heat { background: linear-gradient(135deg, #f97316, #ef4444); }
.sel-kpi-pair {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}
.sel-kpi-label {
  font-size: 12px;
  color: #64748b;
}
.sel-kpi-val {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}
.sel-kpi--short .sel-kpi-val { color: #b45309; }
.sel-kpi-unit {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
}
.sel-kpi-sep {
  color: #cbd5e1;
  font-size: 14px;
}
.sel-cap-alert {
  margin-bottom: 10px;
}

@media (max-width: 640px) {
  .sel-kpi-group { flex: 1 1 100%; }
}
.sub-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 4px 4px 12px;
  border-bottom: 1px dashed #e2e8f0;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.sub-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sub-count {
  font-size: 13px;
  color: #475569;
  font-weight: 600;
}
.sub-count-cap {
  color: #94a3b8;
  font-weight: 500;
}
.sub-toolbar-right {
  display: flex;
  gap: 8px;
}
.sub-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.sub-block {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 14px 16px;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.sub-block:hover {
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}
.sub-block--selected {
  border-color: #f59e0b;
  background: #fffbeb;
}
.sub-block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  margin-bottom: 12px;
  border-bottom: 1px dashed #e2e8f0;
  flex-wrap: wrap;
}
.sub-block-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.sub-idx {
  background: #e0e7ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.sub-name-input {
  max-width: 260px;
}
.empty-sub {
  padding: 24px 0;
}
.mt {
  margin-top: 12px;
}
.issues-card :deep(.el-card__header) {
  padding: 10px 14px;
  font-weight: 600;
}
.issues-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.issues-stat {
  display: flex;
  gap: 6px;
}
</style>
