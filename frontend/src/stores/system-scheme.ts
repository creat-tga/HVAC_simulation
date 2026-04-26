/**
 * System Scheme store — project-level scheme list + active scheme detail editor.
 *
 * Layout:
 *  - List page (cards): uses `items` (lightweight list)
 *  - Detail page: uses `activeScheme` (full tree with subsystems/combos/towers)
 */

import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import {
  createScheme,
  deleteScheme,
  getScheme,
  getSchemeBundle,
  getSchemeDerived,
  getSchemeSummary,
  listSchemes,
  updateScheme,
  validateProjectSchemes,
  validateScheme,
  validateSchemePayload,
  validateStrategy,
  validateStrategyPayload,
} from '@/api/system-scheme'
import type {
  CapacitySummary,
  SchemeDerived,
  SystemScheme,
  SystemSchemeCreate,
  SystemSchemeListItem,
  SystemSchemeUpdate,
  ValidationReport,
} from '@/types/system-scheme'

export const useSystemSchemeStore = defineStore('systemScheme', () => {
  // list page
  const items = ref<SystemSchemeListItem[]>([])
  const loadingList = ref(false)

  // detail page
  const activeScheme = ref<SystemScheme | null>(null)
  const summary = ref<CapacitySummary | null>(null)
  // derived / validation / projectValidation 仅用于只读展示，使用 shallowRef
  // 避免 Vue 对其深度创建 Proxy（千余字段的嵌套结构在子组件渲染时
  // 会严重拖慢 el-descriptions / el-input-number 的初次挂载。
  const derived = shallowRef<SchemeDerived | null>(null)
  const validation = shallowRef<ValidationReport | null>(null)
  const projectValidation = shallowRef<ValidationReport | null>(null)
  const loadingDetail = ref(false)
  const dirty = ref(false)

  // ---------------- list ----------------
  async function fetchList(projectId: string) {
    loadingList.value = true
    // 清空上次项目级校验结果，避免列表页显示过期 issues
    projectValidation.value = null
    try {
      const { data } = await listSchemes(projectId)
      items.value = data.sort((a, b) => a.scheme_index - b.scheme_index)
    } finally {
      loadingList.value = false
    }
  }

  async function add(projectId: string, data: SystemSchemeCreate) {
    const { data: scheme } = await createScheme(projectId, data)
    await fetchList(projectId)
    return scheme
  }

  async function remove(projectId: string, schemeId: string) {
    await deleteScheme(schemeId)
    items.value = items.value.filter((i) => i.id !== schemeId)
    if (activeScheme.value?.id === schemeId) {
      activeScheme.value = null
      summary.value = null
      derived.value = null
    }
    await fetchList(projectId)
  }

  async function validateProject(projectId: string) {
    const { data } = await validateProjectSchemes(projectId)
    projectValidation.value = data
    return data
  }

  // ---------------- detail ----------------
  async function fetchDetail(schemeId: string) {
    loadingDetail.value = true
    // 清空上次遵从未保存 payload 校验的 issues：
    // 否则用户修改后未保存切换页面重进后，
    // activeScheme 已重拉为最后一次保存的数值，
    // 但舊的 issues 仍会在置顶 / 子项高亮 / 保存拦截处出现。
    validation.value = null
    try {
      const { data } = await getSchemeBundle(schemeId)
      activeScheme.value = data.scheme
      summary.value = data.summary
      derived.value = data.derived
      dirty.value = false
    } finally {
      loadingDetail.value = false
    }
  }

  async function refreshDerivedAndSummary(schemeId: string) {
    const [{ data: sum }, { data: der }] = await Promise.all([
      getSchemeSummary(schemeId),
      getSchemeDerived(schemeId),
    ])
    summary.value = sum
    derived.value = der
  }

  async function save(schemeId: string, data: SystemSchemeUpdate) {
    const { data: scheme } = await updateScheme(schemeId, data)
    activeScheme.value = scheme
    await refreshDerivedAndSummary(schemeId)
    dirty.value = false
    return scheme
  }

  async function validateActive(schemeId: string) {
    const { data } = await validateScheme(schemeId)
    validation.value = data
    return data
  }

  /**
   * Dry-run validate the unsaved local payload (no DB write). Updates
   * `validation` so existing alerts stay in sync, then returns the report
   * so callers can decide whether to proceed with save.
   */
  async function validatePayload(schemeId: string, data: SystemSchemeUpdate) {
    const { data: rep } = await validateSchemePayload(schemeId, data)
    validation.value = rep
    return rep
  }

  async function validateStrategyActive(schemeId: string) {
    const { data } = await validateStrategy(schemeId)
    validation.value = data
    return data
  }

  async function validateStrategyPayloadOnly(schemeId: string, data: SystemSchemeUpdate) {
    const { data: rep } = await validateStrategyPayload(schemeId, data)
    validation.value = rep
    return rep
  }

  function markDirty() {
    dirty.value = true
  }

  function $reset() {
    items.value = []
    activeScheme.value = null
    summary.value = null
    derived.value = null
    validation.value = null
    projectValidation.value = null
    dirty.value = false
  }

  // ---------------- helpers ----------------
  const coolingShort = computed(
    () =>
      summary.value &&
      summary.value.cooling_load_peak !== null &&
      summary.value.cooling_capacity_total < summary.value.cooling_load_peak,
  )
  const heatingShort = computed(
    () =>
      summary.value &&
      summary.value.heating_load_peak !== null &&
      summary.value.heating_load_peak > 0 &&
      summary.value.heating_capacity_total < summary.value.heating_load_peak,
  )
  const capacityShort = computed(() => coolingShort.value || heatingShort.value)

  return {
    // list
    items,
    loadingList,
    fetchList,
    add,
    remove,
    validateProject,
    projectValidation,
    // detail
    activeScheme,
    summary,
    derived,
    validation,
    loadingDetail,
    dirty,
    fetchDetail,
    refreshDerivedAndSummary,
    save,
    validateActive,
    validatePayload,
    validateStrategyActive,
    validateStrategyPayloadOnly,
    markDirty,
    coolingShort,
    heatingShort,
    capacityShort,
    $reset,
  }
})
