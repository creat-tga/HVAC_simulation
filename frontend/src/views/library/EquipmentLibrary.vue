<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Edit } from '@element-plus/icons-vue'
import {
  listEquipment,
  createEquipment,
  updateEquipment,
  deleteEquipment,
} from '@/api/library'
import type { EquipmentModel, EquipmentType } from '@/types/library'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()

const tab = ref<'all' | 'public' | 'mine'>('all')
const typeFilter = ref<EquipmentType | ''>('')
const list = ref<EquipmentModel[]>([])
const loading = ref(false)

const TYPES: EquipmentType[] = ['chiller', 'heat_pump', 'cooling_tower', 'pump', 'boiler', 'fan', 'other']

async function load() {
  loading.value = true
  try {
    const { data } = await listEquipment({
      scope: tab.value,
      equipment_type: typeFilter.value || undefined,
    })
    list.value = data
  } finally {
    loading.value = false
  }
}

onMounted(load)

// Form
const dlg = ref(false)
const isEdit = ref(false)
const editId = ref('')
const form = ref({
  name: '',
  equipment_type: 'chiller' as EquipmentType,
  brand: '',
  model_no: '',
  capacity: undefined as number | undefined,
  cop: undefined as number | undefined,
  description: '',
  is_public: false,
})

function openCreate() {
  isEdit.value = false
  editId.value = ''
  form.value = {
    name: '',
    equipment_type: 'chiller',
    brand: '',
    model_no: '',
    capacity: undefined,
    cop: undefined,
    description: '',
    is_public: false,
  }
  dlg.value = true
}

function openEdit(eq: EquipmentModel) {
  isEdit.value = true
  editId.value = eq.id
  form.value = {
    name: eq.name,
    equipment_type: eq.equipment_type,
    brand: eq.brand || '',
    model_no: eq.model_no || '',
    capacity: eq.capacity || undefined,
    cop: eq.cop || undefined,
    description: eq.description || '',
    is_public: eq.is_public,
  }
  dlg.value = true
}

async function handleSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.warning(t('common.required'))
    return
  }
  if (isEdit.value) {
    await updateEquipment(editId.value, form.value)
    ElMessage.success(t('common.updateSuccess'))
  } else {
    await createEquipment(form.value)
    ElMessage.success(t('common.createSuccess'))
  }
  dlg.value = false
  await load()
}

async function handleDelete(eq: EquipmentModel) {
  await ElMessageBox.confirm(t('common.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteEquipment(eq.id)
  ElMessage.success(t('common.deleteSuccess'))
  await load()
}

const canEdit = (eq: EquipmentModel) => auth.isAdmin || (!eq.is_public)
</script>

<template>
  <div class="lib-view">
    <div class="lib-header">
      <h1>{{ t('lib.equipment.title') }}</h1>
      <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('lib.equipment.create') }}</el-button>
    </div>

    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane :label="t('lib.scope.all')" name="all" />
      <el-tab-pane :label="t('lib.scope.public')" name="public" />
      <el-tab-pane :label="t('lib.scope.mine')" name="mine" />
    </el-tabs>

    <div class="filter-bar">
      <el-select v-model="typeFilter" :placeholder="t('lib.equipment.allTypes')" clearable style="width: 180px" @change="load">
        <el-option v-for="ty in TYPES" :key="ty" :label="t(`lib.equipment.types.${ty}`)" :value="ty" />
      </el-select>
    </div>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="name" :label="t('common.name')" min-width="160" show-overflow-tooltip />
      <el-table-column :label="t('lib.equipment.type')" width="120">
        <template #default="{ row }">{{ t(`lib.equipment.types.${row.equipment_type}`) }}</template>
      </el-table-column>
      <el-table-column prop="brand" :label="t('lib.equipment.brand')" width="120" />
      <el-table-column prop="model_no" :label="t('lib.equipment.modelNo')" width="120" />
      <el-table-column :label="t('lib.equipment.capacity')" width="100" align="right">
        <template #default="{ row }">{{ row.capacity?.toFixed(1) || '-' }} kW</template>
      </el-table-column>
      <el-table-column prop="cop" :label="'COP'" width="80" align="right">
        <template #default="{ row }">{{ row.cop?.toFixed(2) || '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('lib.scope.label')" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_public" type="success" size="small">{{ t('lib.public') }}</el-tag>
          <el-tag v-else type="info" size="small">{{ t('lib.scope.mine') }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('common.operation')" width="120">
        <template #default="{ row }">
          <el-button v-if="canEdit(row)" size="small" :icon="Edit" text @click="openEdit(row)" />
          <el-button v-if="canEdit(row)" size="small" type="danger" :icon="Delete" text @click="handleDelete(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dlg" :title="isEdit ? t('lib.equipment.edit') : t('lib.equipment.create')" width="540px">
      <el-form label-width="100px">
        <el-form-item :label="t('common.name')" required>
          <el-input v-model="form.name" :maxlength="100" />
        </el-form-item>
        <el-form-item :label="t('lib.equipment.type')">
          <el-select v-model="form.equipment_type" style="width: 100%">
            <el-option v-for="ty in TYPES" :key="ty" :label="t(`lib.equipment.types.${ty}`)" :value="ty" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('lib.equipment.brand')">
          <el-input v-model="form.brand" />
        </el-form-item>
        <el-form-item :label="t('lib.equipment.modelNo')">
          <el-input v-model="form.model_no" />
        </el-form-item>
        <el-form-item :label="t('lib.equipment.capacity')">
          <el-input-number v-model="form.capacity" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="COP">
          <el-input-number v-model="form.cop" :min="0" :precision="2" :step="0.1" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('common.description')">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="auth.isAdmin" :label="t('lib.public')">
          <el-switch v-model="form.is_public" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSubmit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lib-view { padding: 24px 28px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.lib-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.lib-header h1 { margin: 0; font-size: 22px; color: #0f172a; }
.filter-bar { margin-bottom: 12px; }
</style>
