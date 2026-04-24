<script setup lang="ts">
/**
 * SubsystemEditor — 单个子系统的设备选型容器：
 *   - 设计参数
 *   - 组合编辑器（冷机/风冷模块 + 水泵）
 *   - 冷却塔编辑器（仅 chiller_plant）
 *
 * 通过 v-model 双向绑定整个 Subsystem 对象到父组件。
 */
import { computed } from 'vue'
import DesignParamsForm from './DesignParamsForm.vue'
import ComboEditor from './ComboEditor.vue'
import TowerGroupEditor from './TowerGroupEditor.vue'
import type {
  Subsystem,
  SubsystemDerived,
  ValidationIssue,
} from '@/types/system-scheme'

const props = defineProps<{
  modelValue: Subsystem
  derived: SubsystemDerived | null
  issues?: ValidationIssue[]
}>()
const emit = defineEmits<{ 'update:modelValue': [v: Subsystem] }>()

function update<K extends keyof Subsystem>(key: K, val: Subsystem[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}

const pipeSystem = computed<'two_pipe' | 'four_pipe'>(() => {
  const dp = props.modelValue.design_params || {}
  return ((dp as Record<string, unknown>).pipe_system as 'two_pipe' | 'four_pipe') || 'two_pipe'
})

/**
 * Subsystem-level orphan issues — those bound to this subsystem but not to
 * a specific combo / tower group. Examples: CP_EVAP_DP, CAP_COOL/CAP_HEAT
 * mismatches, etc. Without this section those errors would never be
 * surfaced inline because no child component owns them.
 */
const subsystemLevelIssues = computed<ValidationIssue[]>(() => {
  const list = (props.issues || []).filter((i) => {
    if (i.combo_id) return false
    // Tower-group-related issues are surfaced inside TowerGroupEditor —
    // skip them here to avoid double-rendering the same alert.
    if (i.field?.startsWith('tower_groups[')) return false
    if (i.code?.startsWith('CP_TOWER_')) return false
    return true
  })
  return [...list].sort(
    (a, b) => (a.severity === 'error' ? 0 : 1) - (b.severity === 'error' ? 0 : 1),
  )
})
const hasSubsystemError = computed(() =>
  subsystemLevelIssues.value.some((i) => i.severity === 'error'),
)
</script>

<template>
  <div class="sub-editor">
    <!-- Subsystem-level orphan issues (e.g. CP_EVAP_DP, capacity mismatches)
         that aren't tied to a specific combo/tower row. -->
    <div
      v-if="subsystemLevelIssues.length"
      class="subsystem-issues"
      :class="{ 'has-error': hasSubsystemError }"
    >
      <el-alert
        v-for="(iss, i) in subsystemLevelIssues"
        :key="i"
        :type="iss.severity === 'error' ? 'error' : 'warning'"
        :title="iss.message"
        show-icon
        :closable="false"
        class="sub-issue-alert"
      />
    </div>

    <DesignParamsForm
      :model-value="modelValue.design_params"
      :scheme-type="modelValue.subsystem_type"
      @update:model-value="(v) => update('design_params', v)"
    />

    <ComboEditor
      class="mt"
      :model-value="modelValue.combos"
      :scheme-type="modelValue.subsystem_type"
      :pipe-system="pipeSystem"
      :derived="derived?.combos"
      :issues="issues || []"
      @update:model-value="(v) => update('combos', v)"
    />

    <TowerGroupEditor
      v-if="modelValue.subsystem_type === 'chiller_plant'"
      class="mt"
      :model-value="modelValue.tower_groups"
      :derived="derived"
      :issues="issues || []"
      @update:model-value="(v) => update('tower_groups', v)"
    />

    <el-empty
      v-if="modelValue.subsystem_type === 'shared_tower'"
      :description="$t('scheme.sharedTowerTba')"
    />
  </div>
</template>

<style scoped>
.sub-editor {
  display: block;
}
.mt {
  margin-top: 12px;
}
.subsystem-issues {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.sub-issue-alert {
  padding: 6px 10px;
}
</style>
