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
import { ElMessage, ElMessageBox, ElCard } from 'element-plus'
import { ArrowLeft, Plus, Check, Setting, Delete, ArrowDown, ArrowRight, FolderChecked } from '@element-plus/icons-vue'
import { randomUUID } from '@/utils/uuid'
import { getBuilding } from '@/api/buildings'
import { useSystemSchemeStore } from '@/stores/system-scheme'
import { useResponsive } from '@/composables/useResponsive'
import SubsystemEditor from '@/components/scheme/SubsystemEditor.vue'
import ControlStrategyEditor from '@/components/scheme/ControlStrategyEditor.vue'
import type { Building } from '@/types/building'
import type {
  ControlStrategy,
  Subsystem,
  SubsystemDerived,
  SubsystemType,
  StrategyStep,
  SystemSchemeUpdate,
  ValidationIssue,
} from '@/types/system-scheme'
import { ensureControlStrategy } from '@/utils/control-strategy'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useSystemSchemeStore()
const { isMobile } = useResponsive()

const projectId = computed(() => route.params.projectId as string)
const schemeId = computed(() => route.params.schemeId as string)

// 校验问题：存在 error 时仅展示 error；error 全部修复后再展示 warning
const visibleIssues = computed(() => {
  const all = store.validation?.issues || []
  const errors = all.filter((i) => i.severity === 'error')
  return errors.length ? errors : all
})

const derivedBySubId = computed(() => {
  const map = new Map<string, SubsystemDerived>()
  for (const sub of store.derived?.subsystems || []) {
    map.set(sub.id, sub)
  }
  return map
})

const issuesBySubId = computed(() => {
  const map = new Map<string, typeof visibleIssues.value>()
  for (const issue of visibleIssues.value) {
    if (!issue.subsystem_id) continue
    const list = map.get(issue.subsystem_id) || []
    list.push(issue)
    map.set(issue.subsystem_id, list)
  }
  return map
})

function derivedForSub(sub: Subsystem | undefined) {
  return sub?.id ? derivedBySubId.value.get(sub.id) || null : null
}

function issuesForSub(sub: Subsystem | undefined) {
  return sub?.id ? issuesBySubId.value.get(sub.id) || [] : []
}

const strategyIssues = computed(() => {
  const all = store.validation?.issues || []
  const strategyOnly = all.filter((i) => i.code.startsWith('STR_') || i.field?.startsWith('control_strategy'))
  const errors = strategyOnly.filter((i) => i.severity === 'error')
  return errors.length ? errors : strategyOnly
})

const normalizedControlStrategy = computed(() =>
  ensureControlStrategy(
    local.control_strategy,
    local.subsystems,
    store.derived?.subsystems,
    building.value?.zones || [],
  ),
)

const wizardStep = ref<'selection' | 'strategy' | 'diagram'>('selection')
// 已挂载过的步骤集合：用于实现"首次进入挂载、之后用 v-show 切换"的缓存策略，避免重复挂载导致的卡顿
const visitedSteps = ref<Set<'selection' | 'strategy' | 'diagram'>>(new Set(['selection']))
watch(wizardStep, (s) => { visitedSteps.value.add(s) })
const STEPS = [
  { key: 'selection' as const, titleKey: 'scheme.steps.selection', subKey: 'scheme.steps.selectionDesc' },
  { key: 'strategy' as const, titleKey: 'scheme.steps.strategy', subKey: 'scheme.steps.tba' },
  { key: 'diagram' as const, titleKey: 'scheme.steps.diagram', subKey: 'scheme.steps.tba' },
]
const stepIdx = computed(() => STEPS.findIndex((s) => s.key === wizardStep.value))
const building = ref<Building | null>(null)
const dirtyByStep = reactive<Record<StrategyStep, boolean>>({
  selection: false,
  strategy: false,
  diagram: false,
})

function syncDirtyFlag() {
  store.dirty = dirtyByStep.selection || dirtyByStep.strategy || dirtyByStep.diagram
}

function setStepDirty(step: StrategyStep, value: boolean) {
  dirtyByStep[step] = value
  syncDirtyFlag()
}

function clearAllDirty() {
  dirtyByStep.selection = false
  dirtyByStep.strategy = false
  dirtyByStep.diagram = false
  syncDirtyFlag()
}

function revertStep(step: StrategyStep) {
  const s = store.activeScheme
  if (!s) return
  suppressDirty = true
  if (step === 'selection') {
    local.name = s.name
    local.subsystems = JSON.parse(JSON.stringify(s.subsystems || [])) as Subsystem[]
  } else if (step === 'strategy') {
    local.control_strategy = ensureControlStrategy(
      s.control_strategy,
      s.subsystems || [],
      store.derived?.subsystems,
      building.value?.zones || [],
    )
  }
  void nextTick(() => {
    suppressDirty = false
    setStepDirty(step, false)
  })
}

/**
 * Switch the active wizard step (设备选型 / 控制策略 / 系统图).
 * Each step owns a separate save scope; the current Save button only
 * persists data of the currently visible step. So switching to another
 * step while there are unsaved edits should ask the user to confirm just
 * like the “leave page” guard does.
 */
async function gotoStep(key: 'selection' | 'strategy' | 'diagram') {
  if (key === wizardStep.value) return
  if (dirtyByStep[wizardStep.value]) {
    try {
      await ElMessageBox.confirm(
        t('scheme.leaveWarning'),
        t('common.warning'),
        { type: 'warning', confirmButtonText: t('common.leave'), cancelButtonText: t('common.stay') },
      )
    } catch {
      // user cancelled — stay on the current step
      return
    }
    revertStep(wizardStep.value)
    // 用户放弃当前 step 的脏改动 → 取消挂起的 dry-run 校验，
    // 并清空 store.validation（它可能仍持有基于脏值的 issues），
    // 否则切回该 step 时会显示已被还原数据的过期错误提示。
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer)
      autoSaveTimer = null
    }
    store.validation = null
  }
  wizardStep.value = key
}

const activeSubIdx = ref(0)

// Local mutable model bound to store.activeScheme; mark dirty on change
const local = reactive<{
  name: string
  control_strategy: ControlStrategy
  subsystems: Subsystem[]
}>({
  name: '',
  control_strategy: ensureControlStrategy({}, [], null, []),
  subsystems: [],
})

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
  local.subsystems = JSON.parse(JSON.stringify(s.subsystems || [])) as Subsystem[]
  local.control_strategy = ensureControlStrategy(
    s.control_strategy,
    s.subsystems || [],
    store.derived?.subsystems,
    building.value?.zones || [],
  )
  if (activeSubIdx.value >= local.subsystems.length) activeSubIdx.value = 0
  void nextTick(() => {
    suppressDirty = false
    // Force-clear in case the watcher already queued a markDirty earlier.
    clearAllDirty()
  })
}

watch(() => store.activeScheme?.id, syncFromStore)

// ---- 实时校验与脱水状态跟踪（不再自动保存） ----
// 以前这里会在 700ms 间隔后静默执行 store.save，导致
// store.dirty 总是被清零，“未保存提醒”几乎不会触发。
// 现在其他都保留（debounce 后调用 dry-run validate-payload 刷新高亮），
// 但不再自动提交，从而保留 dirty 标记。
watch(
  () => [local.name, local.subsystems] as const,
  () => {
    if (!store.activeScheme) return
    if (suppressDirty || autoSaving) return
    setStepDirty('selection', true)
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    autoSaveTimer = setTimeout(async () => {
      if (!local.name.trim()) return
      try {
        // Refresh validation-only so inline highlights stay in sync with edits.
        const payload = buildSelectionPayload()
        await store.validatePayload(schemeId.value, payload)
      } catch {
        // ignore background validation errors silently
      }
    }, 700)
  },
  { deep: true },
)

watch(
  () => local.control_strategy,
  () => {
    if (!store.activeScheme) return
    if (suppressDirty || autoSaving) return
    setStepDirty('strategy', true)
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    autoSaveTimer = setTimeout(async () => {
      try {
        await store.validateStrategyPayloadOnly(schemeId.value, buildStrategyPayload())
      } catch {
        // ignore background validation errors silently
      }
    }, 700)
  },
  { deep: true },
)

// ----- Subsystem add/remove + selection -----
const MAX_SUBSYSTEMS = 5
const addSubDialogVisible = ref(false)
const newSubType = ref<SubsystemType>('chiller_plant')

const selectMode = ref(false)
const selectedIdx = ref<Set<number>>(new Set())

// Per-subsystem expanded state. Default: all collapsed on initial load to keep
// first-paint snappy when the scheme has multiple subsystems with many combos.
// Newly added subsystems are auto-expanded so the user can immediately edit.
const expandedSubs = ref<Set<string>>(new Set())
// 已挂载过的子系统：一旦展开，便保留挂载，后续折叠/再展开仅切换 v-show，避免重复挂载导致卡顿。
const mountedSubs = ref<Set<string>>(new Set())
function subKey(sub: Subsystem, idx: number): string {
  return sub.id || `idx-${idx}`
}
function isSubExpanded(sub: Subsystem, idx: number): boolean {
  return expandedSubs.value.has(subKey(sub, idx))
}
function isSubMounted(sub: Subsystem, idx: number): boolean {
  return mountedSubs.value.has(subKey(sub, idx))
}
function toggleSubExpanded(sub: Subsystem, idx: number) {
  const k = subKey(sub, idx)
  const s = new Set(expandedSubs.value)
  if (s.has(k)) {
    s.delete(k)
  } else {
    s.add(k)
    if (!mountedSubs.value.has(k)) {
      // 先让骨架同步绘制，再延迟两帧 + 一个微任务挂载真实组件，
      // 给浏览器留出充分时间完成首次绘制，确保用户立刻看到反馈。
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const m = new Set(mountedSubs.value)
          m.add(k)
          mountedSubs.value = m
        })
      })
    }
  }
  expandedSubs.value = s
}
// 子系统最多 5 个，直接渲染外层块更稳定；重组件仍通过 mountedSubs 延迟挂载。

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
    }
  }
  return {}
}

function confirmAddSub() {
  const idx = local.subsystems.length + 1
  const name = `系统${idx}`
  const newId = randomUUID()
  // 默认创建一个组合：冷机 + 冷冻水泵 + 冷却水泵（chiller_plant）/
  // 风冷模块 + 水泵（air_cooled）。结构与 ComboEditor.addCombo 中保持一致，
  // 避免子系统创建后空白无组合。
  const defaultCombo = {
    id: randomUUID(),
    combo_index: 1,
    primary_model_id: null,
    primary_count: 1,
    primary_factor: 0.92,
    group_count: 1,
    chw_pump_model_id: null,
    chw_pump_count: 1,
    chw_pump_backup: 0,
    chw_connection: 'direct' as const,
    chw_pump_factor: 0.77,
    cw_pump_model_id: null,
    cw_pump_count: 1,
    cw_pump_backup: 0,
    cw_connection: 'direct' as const,
    cw_pump_factor: 0.77,
  }
  local.subsystems.push({
    // Pre-assign a stable id so dry-run /validate-payload can echo
    // subsystem_id back and ComboEditor / TowerGroupEditor can match
    // issues to this subsystem before the first save round-trip.
    id: newId,
    subsystem_index: idx,
    subsystem_type: newSubType.value,
    name,
    design_params: defaultDesignParams(newSubType.value),
    combos: [defaultCombo],
    tower_groups: newSubType.value === 'chiller_plant'
      ? [{ id: randomUUID(), group_index: 1, tower_model_id: null, count: 1, factor: 0.85 }]
      : [],
  })
  activeSubIdx.value = local.subsystems.length - 1
  // Auto-expand the newly added subsystem so the user can edit immediately.
  const s = new Set(expandedSubs.value)
  s.add(newId)
  expandedSubs.value = s
  // 新加项立即标记为已挂载，避免首次展开时再延迟一帧。
  const m = new Set(mountedSubs.value)
  m.add(newId)
  mountedSubs.value = m
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
const focusedIssue = ref<ValidationIssue | null>(null)
const focusToken = ref(0)

function buildSelectionPayload(): SystemSchemeUpdate {
  return {
    name: local.name,
    subsystems: local.subsystems,
  }
}

function buildStrategyPayload(): SystemSchemeUpdate {
  return {
    control_strategy: normalizedControlStrategy.value,
  }
}

/**
 * Scroll to the first issue in a validation report. Errors take precedence;
 * if only warnings exist, the first warning alert is highlighted instead.
 * Also switches the active subsystem tab so the issue is visible.
 */
function expandSubForIssue(issue: ValidationIssue) {
  if (!issue.subsystem_id) return -1
  const idx = local.subsystems.findIndex((s) => s.id === issue.subsystem_id)
  if (idx < 0) return -1
  const key = subKey(local.subsystems[idx], idx)
  const expanded = new Set(expandedSubs.value)
  expanded.add(key)
  expandedSubs.value = expanded
  const mounted = new Set(mountedSubs.value)
  mounted.add(key)
  mountedSubs.value = mounted
  return idx
}

function issueSelector(issue: ValidationIssue, hasErrors: boolean): string {
  const alertClass = hasErrors ? '.el-alert--error' : '.el-alert--warning'
  if (issue.combo_id) {
    return `[data-combo-id="${issue.combo_id}"] ${alertClass}, [data-combo-id="${issue.combo_id}"]`
  }
  if (issue.subsystem_id) {
    return `[data-subsystem-id="${issue.subsystem_id}"] ${alertClass}, [data-subsystem-id="${issue.subsystem_id}"] .subsystem-issues, [data-subsystem-id="${issue.subsystem_id}"]`
  }
  return alertClass
}

function locateFirstIssue(rep: { issues: ValidationIssue[] }) {
  if (!rep.issues.length) return
  const errors = rep.issues.filter((i) => i.severity === 'error')
  const first = errors[0] || rep.issues[0]
  const isStrategyIssue = first.field?.startsWith('control_strategy')
  if (isStrategyIssue) wizardStep.value = 'strategy'
  else wizardStep.value = 'selection'
  focusedIssue.value = first
  focusToken.value += 1
  const subIdx = isStrategyIssue ? -1 : expandSubForIssue(first)
  if (subIdx >= 0) {
    activeSubIdx.value = subIdx
    void nextTick(() => {
      document.querySelector(`[data-subsystem-index="${subIdx}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
  }
  setTimeout(() => {
    let target: Element | null = null
    if (isStrategyIssue) {
      target = document.querySelector('.strategy-page .el-alert--error')
        || document.querySelector('.strategy-page .el-alert--warning')
    } else {
      target = document.querySelector(issueSelector(first, !!errors.length))
    }
    if (!target) {
      // Fallback for issues that are not attached to a combo/subsystem-specific alert.
      if (errors.length) {
        target = document.querySelector('.combo-block.has-error, .tower-row.has-error')
          || document.querySelector('.subsystem-issues.has-error')
          || document.querySelector('.el-alert--error')
      } else {
        target = document.querySelector('.el-alert--warning')
      }
    }
    if (target) (target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 450)
}

async function save() {
  if (!local.name.trim()) {
    ElMessage.warning(t('scheme.namePlaceholder'))
    return
  }
  saving.value = true
  try {
    if (wizardStep.value === 'selection') {
      const payload = buildSelectionPayload()
      const pre = await store.validatePayload(schemeId.value, payload)
      const preErrors = pre.issues.filter((i) => i.severity === 'error')
      if (preErrors.length) {
        ElMessage.error(t('scheme.saveBlockedByErrors', { n: preErrors.length }))
        locateFirstIssue(pre)
        return
      }
      await store.save(schemeId.value, payload)
      syncFromStore()
      const rep = await store.validateActive(schemeId.value)
      ElMessage.success({ message: t('common.saved'), duration: 1200 })
      if (rep.issues.length) {
        const warns = rep.issues.filter((i) => i.severity === 'warning')
        if (warns.length) {
          ElMessage.warning(t('scheme.savedWithWarnings', { n: warns.length }))
        }
        locateFirstIssue(rep)
      }
      return
    }
    if (wizardStep.value === 'strategy') {
      const payload = buildStrategyPayload()
      const pre = await store.validateStrategyPayloadOnly(schemeId.value, payload)
      const preErrors = pre.issues.filter((i) => i.severity === 'error')
      if (preErrors.length) {
        ElMessage.error(t('scheme.saveBlockedByErrors', { n: preErrors.length }))
        locateFirstIssue(pre)
        return
      }
      await store.save(schemeId.value, payload)
      syncFromStore()
      const rep = await store.validateStrategyActive(schemeId.value)
      ElMessage.success({ message: t('common.saved'), duration: 1200 })
      if (rep.issues.length) {
        const warns = rep.issues.filter((i) => i.severity === 'warning')
        if (warns.length) {
          ElMessage.warning(t('scheme.savedWithWarnings', { n: warns.length }))
        }
        locateFirstIssue(rep)
      }
      return
    }
    ElMessage.warning(t('scheme.steps.tba'))
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
  // 桌面端：锁外层滚动，让内部 .ssd-body 独立滚动，
  // 保留顶部步骤条常驻。
  // 移动端：不锁，改为整个页面自然滚动。
  // 原因：移动端子系统多时 reactive Proxy 创建 + 深拷贝可
  // 能阻塞主线程，且嵌套滚动容器在手机上容易丢触摸
  // 事件产生“卡住”。
  if (!isMobile.value) {
    const wsContent = document.querySelector('.ws-content') as HTMLElement | null
    if (wsContent) {
      wsContent.dataset.prevOverflow = wsContent.style.overflow
      wsContent.style.overflow = 'hidden'
    }
  }
  await store.fetchDetail(schemeId.value)
  // 先用 scheme 数据立即渲染页面（设备选型不依赖 building 详情）
  syncFromStore()
  // 后台并发拉取 building，到达后重新同步 control_strategy 的 zones
  if (store.activeScheme?.building_id) {
    getBuilding(projectId.value, store.activeScheme.building_id)
      .then(({ data }) => {
        building.value = data
        syncFromStore()
      })
      .catch(() => { building.value = null })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnload)
  // 取消 pending 的 debounced 校验，避免路由切换后 timer 触发
  // 把基于「未保存的脏值」的 issues 写回 store，造成下次进入页面残留旧错误。
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }
  // 主动清理 store 中由 dry-run 校验留下的 issues。
  store.validation = null
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
  <div v-loading="store.loadingDetail && !store.activeScheme" class="ssd-page">
    <!-- ============== MOBILE TOPBAR：teleport 到 layout 中、位于 .ws-content 之外，真正不滚动 ============== -->
    <Teleport v-if="isMobile" to="#ws-mobile-topbar-slot" defer>
      <div class="ssd-mobile-topbar">
        <button class="ssd-mb-back" :aria-label="t('workspace.backToProjects') || '返回'" @click="goBackToList">
          <el-icon :size="20"><ArrowLeft /></el-icon>
        </button>
        <div class="ssd-mb-seg" role="tablist">
          <button
            v-for="(s, i) in STEPS"
            :key="s.key"
            type="button"
            role="tab"
            :aria-selected="wizardStep === s.key"
            class="ssd-mb-seg-btn"
            :class="{ active: wizardStep === s.key }"
            @click="gotoStep(s.key)"
          >
            <span class="ssd-mb-seg-num">{{ i + 1 }}</span>
            <span class="ssd-mb-seg-label">{{ t(s.titleKey) }}</span>
          </button>
        </div>
        <el-badge is-dot :hidden="!store.dirty" type="danger" class="ssd-mb-save-badge">
          <button
            class="ssd-mb-save"
            :disabled="saving"
            :aria-label="t('common.save')"
            @click="save"
          >
            <el-icon v-if="!saving" :size="16"><FolderChecked /></el-icon>
            <el-icon v-else :size="16" class="is-loading"><Setting /></el-icon>
          </button>
        </el-badge>
      </div>
    </Teleport>

    <!-- ============== TOP BAR (desktop only: name readonly + steps + save) ============== -->
    <div v-if="!isMobile" class="ssd-topbar">
      <div class="topbar-name-readonly" :title="local.name">{{ local.name || t('scheme.namePlaceholder') }}</div>
      <div class="topbar-steps">
        <el-tooltip
          v-for="(s, i) in STEPS"
          :key="s.key"
          :content="t(s.titleKey)"
          placement="bottom"
          :show-after="200"
        >
          <div
            class="stepitem"
            :class="{
              active: wizardStep === s.key,
              done: stepIdx > i,
              pending: stepIdx < i,
            }"
            @click="gotoStep(s.key)"
          >
            <div class="step-circle">
              <el-icon v-if="stepIdx > i"><Check /></el-icon>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <div class="step-title">{{ t(s.titleKey) }}</div>
          </div>
        </el-tooltip>
      </div>
      <el-badge is-dot :hidden="!store.dirty" type="danger" class="topbar-save">
        <el-button type="primary" :icon="FolderChecked" :loading="saving" @click="save" size="default">
          {{ t('common.save') }}
        </el-button>
      </el-badge>
    </div>

    <!-- ============== STEP BODY ==============
         移动端：直接用 div 容器，不渲染 el-card 外壳；
         桌面端：使用 el-card 提供视觉分组。 -->
    <component :is="isMobile ? 'div' : ElCard" class="ssd-body" :shadow="isMobile ? undefined : 'never'">
      <div v-if="visitedSteps.has('selection')" v-show="wizardStep === 'selection'">
        <el-form label-position="top" :inline="false" @submit.prevent>
        <!-- KPI: 冷热负荷 vs 装机容量（紧凑单行展示） -->
        <div class="sel-kpi">
          <div class="sel-kpi-group" :class="{ 'sel-kpi--short': coolingShort }">
            <span class="sel-kpi-tag sel-kpi-tag--cool">{{ t('scheme.summary.cooling') || '制冷' }}</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label"><span class="kw">负荷</span><span class="kw">峰值</span></span>
              <span class="sel-kpi-val">{{ store.summary?.cooling_load_peak !== null && store.summary?.cooling_load_peak !== undefined ? store.summary.cooling_load_peak.toFixed(1) : '-' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
            <span class="sel-kpi-sep">/</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label"><span class="kw">装机</span><span class="kw">容量</span></span>
              <span class="sel-kpi-val">{{ store.summary?.cooling_capacity_total?.toFixed(1) ?? '0.0' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
          </div>
          <div class="sel-kpi-group" :class="{ 'sel-kpi--short': heatingShort }">
            <span class="sel-kpi-tag sel-kpi-tag--heat">{{ t('scheme.summary.heating') || '制热' }}</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label"><span class="kw">负荷</span><span class="kw">峰值</span></span>
              <span class="sel-kpi-val">{{ store.summary?.heating_load_peak !== null && store.summary?.heating_load_peak !== undefined ? store.summary.heating_load_peak.toFixed(1) : '-' }}</span>
              <span class="sel-kpi-unit">kW</span>
            </span>
            <span class="sel-kpi-sep">/</span>
            <span class="sel-kpi-pair">
              <span class="sel-kpi-label"><span class="kw">装机</span><span class="kw">容量</span></span>
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
            <el-button plain :icon="Plus" @click="openAddSub">
              {{ t('scheme.addSubsystem') }}
            </el-button>
          </el-empty>
        </div>

        <!-- Vertical stack of subsystems -->
        <div v-else class="sub-stack">
          <template v-for="(sub, subIdx) in local.subsystems" :key="subKey(sub, subIdx)">
            <div
              class="sub-block"
              :class="{ 'sub-block--selected': selectMode && selectedIdx.has(subIdx), 'sub-block--collapsed': !isSubExpanded(sub, subIdx) }"
              :data-subsystem-id="sub.id || undefined"
              :data-subsystem-index="subIdx"
            >
            <div class="sub-block-head">
              <div class="sub-block-head-left">
                <el-checkbox
                  v-if="selectMode"
                  :model-value="selectedIdx.has(subIdx)"
                  @change="toggleSelect(subIdx)"
                />
                <el-button
                  size="small"
                  text
                  :icon="isSubExpanded(sub, subIdx) ? ArrowDown : ArrowRight"
                  class="sub-toggle-btn"
                  @click="toggleSubExpanded(sub, subIdx)"
                />
                <span class="sub-idx">系统{{ subIdx + 1 }}</span>
                <el-tag size="small" type="info" effect="plain">
                  {{ t('scheme.types.' + sub.subsystem_type) }}
                </el-tag>
                <span v-if="!isSubExpanded(sub, subIdx)" class="sub-collapsed-info">
                  <template v-for="d in [derivedForSub(sub)]" :key="d?.id || subIdx">
                    <template v-if="d?.cooling_capacity_total">
                      · 制冷量 {{ d.cooling_capacity_total }} kW
                    </template>
                    <template v-if="d?.heating_capacity_total">
                      · 制热量 {{ d.heating_capacity_total }} kW
                    </template>
                  </template>
                </span>
              </div>
              <div class="sub-block-head-right">
                <el-button
                  size="small"
                  type="danger"
                  text
                  :icon="Delete"
                  :disabled="local.subsystems.length <= 1"
                  @click="removeSub(subIdx)"
                >
                  {{ t('common.delete') }}
                </el-button>
              </div>
            </div>

            <SubsystemEditor
              v-if="isSubMounted(sub, subIdx)"
              v-show="isSubExpanded(sub, subIdx)"
              v-model="local.subsystems[subIdx]"
              :derived="derivedForSub(sub)"
              :issues="issuesForSub(sub)"
              :focus-combo-id="focusedIssue?.subsystem_id === sub.id ? focusedIssue?.combo_id || null : null"
              :focus-token="focusToken"
            />
            <!-- 首次展开的过渡骨架：mountedSubs 翻 true 之前先展示，
                 让用户立即看到反馈，避免 1+ s 的"按了没反应"错觉。 -->
            <div
              v-else-if="isSubExpanded(sub, subIdx)"
              class="sub-skeleton"
            >
              <el-skeleton :rows="3" animated />
              <el-skeleton :rows="6" animated style="margin-top: 12px" />
            </div>
            </div>
          </template>
        </div>

        <!-- 校验报告改为就地高亮，无需此处单独表格 -->
        </el-form>
      </div>

      <div v-if="visitedSteps.has('strategy')" v-show="wizardStep === 'strategy'">
        <ControlStrategyEditor
          :model-value="normalizedControlStrategy"
          :subsystems="local.subsystems"
          :derived="store.derived?.subsystems || null"
          :summary="store.summary"
          :zones="building?.zones || []"
          :issues="strategyIssues"
          @update:model-value="(value) => { local.control_strategy = value }"
        />
      </div>

      <div v-if="wizardStep === 'diagram'">
        <el-empty :image-size="120" :description="t('scheme.steps.diagramTba')">
          <el-button disabled>{{ t('scheme.steps.tba') }}</el-button>
        </el-empty>
      </div>
    </component>

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
  padding: 0;
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
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: 6px;
  box-shadow: var(--shadow-sm);
  flex-wrap: nowrap;
  min-width: 0;
}
.topbar-name-readonly {
  flex: 0 0 auto;
  max-width: 220px;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 4px;
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
  border-radius: var(--radius-pill);
  transition: background 0.18s;
  flex-shrink: 0;
}
.stepitem:hover { background: var(--color-neutral-100); }
.stepitem.active {
  background: var(--brand-primary-soft);
}
.step-circle {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-xs);
  background: var(--color-neutral-100);
  color: var(--text-muted);
  border: 2px solid var(--border-subtle);
  flex-shrink: 0;
  transition: all 0.18s;
}
.stepitem.active .step-circle {
  background: var(--brand-primary-gradient);
  color: var(--text-on-brand);
  border-color: transparent;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.28);
}
.stepitem.done .step-circle {
  background: var(--color-success);
  color: var(--text-on-brand);
  border-color: transparent;
}
.step-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: 1.2;
  white-space: nowrap;
}
.stepitem.pending .step-title {
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}
@media (max-width: 900px) {
  /* T-1+T-2: 小屏下顶栏换行，步骤条独立铺满第二行，文字完整保留。 */
  .ssd-topbar {
    flex-wrap: wrap;
    row-gap: 8px;
  }
  .topbar-steps {
    order: 10;
    flex-basis: 100%;
    justify-content: flex-start;
    overflow-x: auto;
    padding-top: 4px;
    border-top: 1px dashed var(--border-subtle);
  }
  .topbar-name-readonly { flex: 1 1 auto; min-width: 0; max-width: none; }
}

.ssd-body {
  border: 1px solid var(--border-subtle);
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  /* 始终预留竖向滚动条空间，避免子系统折叠/展开时滚动条出现/消失导致内容横向跳动。 */
  scrollbar-gutter: stable;
}
.ssd-body :deep(.el-card__body) {
  padding: 10px 12px;
  /* el-card 自身的 body 也是潜在滚动容器，同样预留 gutter。 */
  scrollbar-gutter: stable;
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
  font-size: var(--font-size-sm);
  color: var(--color-neutral-600);
  font-weight: var(--font-weight-medium);
  padding-bottom: 4px !important;
  line-height: 1.3;
}
.ssd-body :deep(.el-form-item) {
  margin-bottom: 14px;
}

/* Keep shared scheme field layout from being overridden by the legacy body rules above. */
.ssd-body :deep(.scheme-field-grid .el-form-item) {
  margin: 0 0 6px 0 !important;
}
.ssd-body :deep(.scheme-field-grid .el-form-item__label) {
  display: flex;
  align-items: center;
  height: var(--scheme-control-height);
  min-height: var(--scheme-control-height);
  padding: 0 !important;
  font-size: var(--scheme-label-font-size);
  font-weight: var(--font-weight-regular);
  line-height: 1.25;
}
.ssd-body :deep(.scheme-field-grid .el-input-number) {
  width: var(--scheme-control-width) !important;
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
  display: flex;
  align-items: center;
  /* flex-wrap: wrap;          /* 允许整体在窄屏换行 */
  row-gap: 4px;
  column-gap: 8px;
  padding: 6px 6px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #f0f9ff 0%, #f5f3ff 100%);
  border: 1px solid var(--border-subtle);
  min-height: 36px;
  /* 中文不按字符断；只在标签的两字之间允许断 */
  word-break: keep-all;
  overflow-wrap: normal;
  line-height: 1.2;
}
.sel-kpi--short {
  border-color: #fcd34d;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
}
.sel-kpi-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-pill);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: #fff;
  flex-shrink: 0;
  line-height: 1;
  white-space: nowrap;
}
.sel-kpi-tag--cool { background: linear-gradient(135deg, #06b6d4, #0ea5e9); }
.sel-kpi-tag--heat { background: linear-gradient(135deg, #f97316, var(--color-danger)); }
.sel-kpi-pair {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  line-height: 1.2;
  /* pair 内允许在 .sel-kpi-label 内的两字之间换行 */
  flex-wrap: wrap;
  row-gap: 2px;
}
.sel-kpi-label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: 1.2;
  /* 关键：只允许在子元素 .kw 之间断行，每个 .kw 内部不断 */
  word-break: keep-all;
  overflow-wrap: normal;
}
.sel-kpi-label .kw {
  display: inline-block;
  white-space: nowrap;
}
.sel-kpi-val {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  line-height: 1.2;
}
.sel-kpi--short .sel-kpi-val { color: #b45309; }
.sel-kpi-unit {
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  color: var(--text-muted);
  white-space: nowrap;
  line-height: 1.2;
}
.sel-kpi-sep {
  color: var(--border-base);
  font-size: var(--font-size-base);
  flex-shrink: 0;
  line-height: 1.2;
}
.sel-cap-alert {
  margin-bottom: 10px;
}

@media (max-width: 640px) {
  .sel-kpi-group { flex: 1 1 100%; }
}

/* 移动端：禁用嵌套滚动，改由外层 .ws-content 整体滚动；
   避免大量子系统/组合首挂载时主线程阻塞 + 嵌套滚动卡死。 */
@media (max-width: 768px) {
  .ssd-page {
    height: auto;
    min-height: 100%;
    /* sticky 顶栏 + 内容自然排列，不需要 padding-top 占位 */
    padding: 0 4px calc(112px + env(safe-area-inset-bottom, 0px));
  }
  .ssd-page::after {
    content: '';
    display: block;
    flex: 0 0 auto;
    height: calc(60px + env(safe-area-inset-bottom, 0px));
  }
  .ssd-body {
    border-color: transparent !important;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    overflow: visible;
    flex: 0 0 auto;
    min-height: 0;
  }
}

/* ============== MOBILE TOPBAR (Teleport 到 .ws-main 内、.ws-content 之外，
   作为普通 flex 项显示在顶部，与外层 TopActionBar 同级，自然"固定"在上方) ============== */
.ssd-mobile-topbar {
  display: flex;
  align-items: center;
  gap: 8px;
  /* 与 TopActionBar.top-bar--mobile 完全一致：透明背景、无边框 */
  padding: 6px 8px;
  background: transparent;
  border: none;
  min-height: 44px;
  flex-shrink: 0;
}
.ssd-mb-back {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-body, #1e293b);
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
}
.ssd-mb-back:active { background: rgba(15, 23, 42, 0.06); }
.ssd-mb-seg {
  flex: 1 1 auto;
  display: inline-flex;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  padding: 2px;
  gap: 2px;
  min-width: 0;
}
.ssd-mb-seg-btn {
  flex: 1 1 0;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 4px;
  font-size: 12px;
  color: var(--text-muted, #64748b);
  background: transparent;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.18s, color 0.18s;
}
.ssd-mb-seg-btn.active {
  background: #ffffff;
  color: var(--text-primary, #0f172a);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.ssd-mb-seg-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  font-size: 10px;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.1);
  color: inherit;
  flex-shrink: 0;
}
.ssd-mb-seg-btn.active .ssd-mb-seg-num {
  background: var(--brand-primary, #6366f1);
  color: #fff;
}
.ssd-mb-seg-label {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ssd-mb-save-badge { flex: 0 0 auto; }
.ssd-mb-save {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.42);
  border-radius: 10px;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.24);
}
.ssd-mb-save:disabled {
  opacity: 0.6;
  box-shadow: none;
}
.ssd-mb-save .is-loading {
  animation: ssd-spin 1s linear infinite;
}
@keyframes ssd-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
/* 极窄屏隐藏文字标签，仅显示数字圆圈 */
@media (max-width: 360px) {
  .ssd-mb-seg-label { display: none; }
}
.sub-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 4px 4px 12px;
  border-bottom: 1px dashed var(--border-subtle);
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.sub-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sub-count {
  font-size: var(--font-size-sm);
  color: var(--color-neutral-600);
  font-weight: var(--font-weight-semibold);
}
.sub-count-cap {
  color: var(--text-muted);
  font-weight: var(--font-weight-medium);
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
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: #fff;
  padding: 14px 16px;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.sub-block:hover {
  box-shadow: var(--shadow-md);
}
.sub-skeleton {
  margin-top: 12px;
  padding: 8px 0;
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
  border-bottom: 1px dashed var(--border-subtle);
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
  background: var(--brand-primary-soft);
  color: var(--brand-primary-active);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
  font-variant-numeric: tabular-nums;
}
.sub-name-input {
  max-width: 260px;
  min-width: 0;
}
.sub-collapsed-info {
  /* \u5b50\u7cfb\u7edf\u6298\u53e0\u6001\u8f7b\u91cf\u4fe1\u606f\uff0c\u5f3a\u5236\u4e0d\u6362\u884c\uff0c\u8fc7\u957f\u7701\u7565\u3002 */
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
@media (max-width: 1024px) {
  /* \u4e2d\u7b49\u5bbd\u5ea6\uff08\u5e73\u677f/\u5206\u5c4f\uff09\u4e0b\uff0chead-left \u5141\u8bb8\u6362\u884c\uff0ccollapsed-info \u72ec\u5360\u4e00\u884c */
  .sub-block-head-left { flex-wrap: wrap; }
  .sub-name-input { max-width: none; flex: 1 1 160px; }
  .sub-collapsed-info {
    flex-basis: 100%;
    max-width: 100%;
    margin-top: 4px;
  }
}
@media (max-width: 480px) {
  /* \u6781\u5c0f\u5c4f\u9690\u85cf\uff0c\u907f\u514d\u65e0\u610f\u4e49\u5360\u4f4d */
  .sub-collapsed-info { display: none; }
}
.empty-sub {
  padding: 24px 0;
}
.mt {
  margin-top: 12px;
}
.issues-card :deep(.el-card__header) {
  padding: 10px 14px;
  font-weight: var(--font-weight-semibold);
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
