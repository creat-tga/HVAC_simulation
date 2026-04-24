<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { searchEquipment } from '@/api/system-scheme'
import type { EquipmentBrief, EquipmentSearchParams } from '@/types/system-scheme'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
  equipmentType: EquipmentSearchParams['equipment_type']
  specOnly?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  pick: [eq: EquipmentBrief]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const tab = ref<'name' | 'spec'>('spec')
const form = reactive({
  name: '',
  capacity_min: undefined as number | undefined,
  capacity_max: undefined as number | undefined,
  flow_min: undefined as number | undefined,
  flow_max: undefined as number | undefined,
  head_min: undefined as number | undefined,
  head_max: undefined as number | undefined,
  efficiency_min: undefined as number | undefined,
  efficiency_max: undefined as number | undefined,
})
const results = ref<EquipmentBrief[]>([])
const loading = ref(false)

async function doSearch() {
  loading.value = true
  try {
    const params: EquipmentSearchParams = { equipment_type: props.equipmentType }
    if (tab.value === 'name') {
      if (form.name) params.name = form.name
    } else {
      if (form.capacity_min) params.capacity_min = form.capacity_min
      if (form.capacity_max) params.capacity_max = form.capacity_max
      if (form.flow_min) params.flow_min = form.flow_min
      if (form.flow_max) params.flow_max = form.flow_max
      if (form.head_min) params.head_min = form.head_min
      if (form.head_max) params.head_max = form.head_max
      if (form.efficiency_min) params.efficiency_min = form.efficiency_min
      if (form.efficiency_max) params.efficiency_max = form.efficiency_max
    }
    const { data } = await searchEquipment(params)
    results.value = data
  } finally {
    loading.value = false
  }
}

watch(visible, (v) => {
  if (v) {
    results.value = []
    void doSearch()
  }
})

function pick(eq: EquipmentBrief) {
  emit('pick', eq)
  visible.value = false
}

const showFlowHead = computed(
  () => props.equipmentType === 'pump' || props.equipmentType === 'cooling_tower',
)
</script>

<template>
  <el-dialog v-model="visible" :title="t('scheme.equipmentSearch.title')" width="780px">
    <el-tabs v-model="tab" v-if="!specOnly">
      <el-tab-pane :label="t('scheme.equipmentSearch.tabName')" name="name">
        <el-form inline>
          <el-form-item :label="t('scheme.equipmentSearch.keyword')">
            <el-input v-model="form.name" style="width: 300px" clearable @keyup.enter="doSearch" />
          </el-form-item>
          <el-button type="primary" @click="doSearch">{{ t('common.search') || '搜索' }}</el-button>
        </el-form>
      </el-tab-pane>
      <el-tab-pane :label="t('scheme.equipmentSearch.tabSpec')" name="spec">
        <el-form inline>
          <el-form-item v-if="!showFlowHead" :label="t('scheme.equipmentSearch.capacityRange')">
            <el-input-number v-model="form.capacity_min" placeholder="min" :min="0" size="small" />
            <span style="margin: 0 6px">~</span>
            <el-input-number v-model="form.capacity_max" placeholder="max" :min="0" size="small" />
          </el-form-item>
          <template v-if="showFlowHead">
            <el-form-item :label="t('scheme.equipmentSearch.flowRange')">
              <el-input-number v-model="form.flow_min" placeholder="min" :min="0" size="small" />
              <span style="margin: 0 6px">~</span>
              <el-input-number v-model="form.flow_max" placeholder="max" :min="0" size="small" />
            </el-form-item>
            <el-form-item v-if="equipmentType === 'pump'" :label="t('scheme.equipmentSearch.headRange')">
              <el-input-number v-model="form.head_min" placeholder="min" :min="0" size="small" />
              <span style="margin: 0 6px">~</span>
              <el-input-number v-model="form.head_max" placeholder="max" :min="0" size="small" />
            </el-form-item>
            <el-form-item v-if="equipmentType === 'pump'" :label="t('scheme.equipmentSearch.efficiencyRange')">
              <el-input-number v-model="form.efficiency_min" placeholder="min" :min="0" :max="1" :step="0.05" :precision="2" size="small" />
              <span style="margin: 0 6px">~</span>
              <el-input-number v-model="form.efficiency_max" placeholder="max" :min="0" :max="1" :step="0.05" :precision="2" size="small" />
            </el-form-item>
          </template>
          <el-button type="primary" @click="doSearch">{{ t('common.search') || '搜索' }}</el-button>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <!-- Spec-only mode: show condition form directly without tabs -->
    <el-form v-else inline class="spec-only-form">
      <el-form-item v-if="!showFlowHead" :label="t('scheme.equipmentSearch.capacityRange')">
        <el-input-number v-model="form.capacity_min" placeholder="min" :min="0" size="small" />
        <span style="margin: 0 6px">~</span>
        <el-input-number v-model="form.capacity_max" placeholder="max" :min="0" size="small" />
      </el-form-item>
      <template v-if="showFlowHead">
        <el-form-item :label="t('scheme.equipmentSearch.flowRange')">
          <el-input-number v-model="form.flow_min" placeholder="min" :min="0" size="small" />
          <span style="margin: 0 6px">~</span>
          <el-input-number v-model="form.flow_max" placeholder="max" :min="0" size="small" />
        </el-form-item>
        <el-form-item v-if="equipmentType === 'pump'" :label="t('scheme.equipmentSearch.headRange')">
          <el-input-number v-model="form.head_min" placeholder="min" :min="0" size="small" />
          <span style="margin: 0 6px">~</span>
          <el-input-number v-model="form.head_max" placeholder="max" :min="0" size="small" />
        </el-form-item>
        <el-form-item v-if="equipmentType === 'pump'" :label="t('scheme.equipmentSearch.efficiencyRange')">
          <el-input-number v-model="form.efficiency_min" placeholder="min" :min="0" :max="1" :step="0.05" :precision="2" size="small" />
          <span style="margin: 0 6px">~</span>
          <el-input-number v-model="form.efficiency_max" placeholder="max" :min="0" :max="1" :step="0.05" :precision="2" size="small" />
        </el-form-item>
      </template>
      <el-button type="primary" @click="doSearch">{{ t('common.search') || '搜索' }}</el-button>
    </el-form>

    <el-table :data="results" v-loading="loading" max-height="380" stripe>
      <el-table-column prop="brand" label="品牌" width="100" />
      <el-table-column prop="model_no" label="型号" width="160" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="容量/COP" width="140">
        <template #default="{ row }">
          <span v-if="row.capacity">{{ row.capacity }} kW</span>
          <span v-if="row.cop"> · COP {{ row.cop }}</span>
        </template>
      </el-table-column>
      <el-table-column label="流量/扬程" width="160">
        <template #default="{ row }">
          <span v-if="row.parameters?.flow">{{ row.parameters.flow }} m³/h</span>
          <span v-if="row.parameters?.head"> · {{ row.parameters.head }} mH₂O</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('scheme.equipmentSearch.pick')" width="80">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="pick(row)">
            {{ t('scheme.equipmentSearch.pick') }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty :description="t('scheme.equipmentSearch.noResult')" />
      </template>
    </el-table>
  </el-dialog>
</template>

<style scoped>
.spec-only-form :deep(.el-form-item) {
  margin-right: 16px;
  margin-bottom: 12px;
}
.spec-only-form :deep(.el-form-item__content) {
  display: inline-flex;
  align-items: center;
  flex-wrap: nowrap;
}
.spec-only-form :deep(.el-input-number) {
  width: 110px !important;
}
.spec-only-form :deep(.el-input-number .el-input__wrapper) {
  padding: 0 8px;
}
</style>
