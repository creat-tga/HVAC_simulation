<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Edit, CopyDocument } from '@element-plus/icons-vue'
import {
  listBuildingTemplates,
  createBuildingTemplate,
  updateBuildingTemplate,
  deleteBuildingTemplate,
  cloneTemplateToProject,
} from '@/api/library'
import { getProjects } from '@/api/projects'
import type { BuildingTemplate } from '@/types/library'
import type { Project } from '@/types/project'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const tab = ref<'all' | 'mine' | 'public'>('all')
const list = ref<BuildingTemplate[]>([])
const loading = ref(false)
const projects = ref<Project[]>([])

async function load() {
  loading.value = true
  try {
    const { data } = await listBuildingTemplates(tab.value)
    list.value = data
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    const { data } = await getProjects()
    projects.value = data
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  await Promise.all([load(), loadProjects()])
})

// ---- Create/Edit ----
const dlg = ref(false)
const isEdit = ref(false)
const editId = ref('')
const form = ref({
  name: '',
  description: '',
  building_type: 'office',
  total_area: undefined as number | undefined,
  floor_count: undefined as number | undefined,
  climate_zone: '',
  is_public: false,
})

function openCreate() {
  isEdit.value = false
  editId.value = ''
  form.value = {
    name: '',
    description: '',
    building_type: 'office',
    total_area: undefined,
    floor_count: undefined,
    climate_zone: '',
    is_public: false,
  }
  dlg.value = true
}

function openEdit(tpl: BuildingTemplate) {
  isEdit.value = true
  editId.value = tpl.id
  form.value = {
    name: tpl.name,
    description: tpl.description || '',
    building_type: tpl.building_type,
    total_area: tpl.total_area || undefined,
    floor_count: tpl.floor_count || undefined,
    climate_zone: tpl.climate_zone || '',
    is_public: tpl.is_public,
  }
  dlg.value = true
}

async function handleSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.warning(t('common.required'))
    return
  }
  if (isEdit.value) {
    await updateBuildingTemplate(editId.value, form.value)
    ElMessage.success(t('common.updateSuccess'))
  } else {
    await createBuildingTemplate(form.value)
    ElMessage.success(t('common.createSuccess'))
  }
  dlg.value = false
  await load()
}

async function handleDelete(tpl: BuildingTemplate) {
  await ElMessageBox.confirm(t('common.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteBuildingTemplate(tpl.id)
  ElMessage.success(t('common.deleteSuccess'))
  await load()
}

// ---- Clone to Project ----
const cloneDlg = ref(false)
const cloningTpl = ref<BuildingTemplate | null>(null)
const cloneTargetProject = ref<string>('')
const cloneNewName = ref<string>('')

function openClone(tpl: BuildingTemplate) {
  cloningTpl.value = tpl
  cloneTargetProject.value = ''
  cloneNewName.value = tpl.name
  cloneDlg.value = true
}

async function doClone() {
  if (!cloneTargetProject.value || !cloningTpl.value) {
    ElMessage.warning(t('lib.tpl.pickProject'))
    return
  }
  const { data } = await cloneTemplateToProject(cloningTpl.value.id, cloneTargetProject.value, cloneNewName.value || undefined)
  ElMessage.success(t('lib.tpl.cloneSuccess'))
  cloneDlg.value = false
  router.push(`/projects/${cloneTargetProject.value}/buildings/${data.id}`)
}

const isOwn = (tpl: BuildingTemplate) => !!tpl.owner_id && tpl.owner_id === auth.username
const canEdit = (tpl: BuildingTemplate) => auth.isAdmin || (!tpl.is_public && isOwn(tpl))
</script>

<template>
  <div class="lib-view">
    <div class="lib-header">
      <h1>{{ t('lib.tpl.title') }}</h1>
      <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('lib.tpl.create') }}</el-button>
    </div>

    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane :label="t('lib.scope.all')" name="all" />
      <el-tab-pane :label="t('lib.scope.public')" name="public" />
      <el-tab-pane :label="t('lib.scope.mine')" name="mine" />
    </el-tabs>

    <div class="lib-grid" v-loading="loading">
      <div v-for="tpl in list" :key="tpl.id" class="tpl-card">
        <div class="tpl-card-head">
          <div class="tpl-name">{{ tpl.name }}</div>
          <el-tag v-if="tpl.is_public" type="success" size="small">{{ t('lib.public') }}</el-tag>
        </div>
        <div class="tpl-meta">
          <span>{{ t(`building.types.${tpl.building_type}`) }}</span>
          <span v-if="tpl.total_area">{{ tpl.total_area }} m²</span>
          <span v-if="tpl.floor_count">{{ tpl.floor_count }} {{ t('building.floors') }}</span>
        </div>
        <p class="tpl-desc" :title="tpl.description || ''">{{ tpl.description || t('common.noDescription') }}</p>
        <div class="tpl-actions">
          <el-button size="small" type="primary" :icon="CopyDocument" @click="openClone(tpl)">
            {{ t('lib.tpl.useInProject') }}
          </el-button>
          <el-button v-if="canEdit(tpl)" size="small" :icon="Edit" @click="openEdit(tpl)" />
          <el-button v-if="canEdit(tpl)" size="small" type="danger" :icon="Delete" @click="handleDelete(tpl)" />
        </div>
      </div>
      <el-empty v-if="!loading && list.length === 0" :description="t('common.noData')" style="grid-column: 1 / -1" />
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dlg" :title="isEdit ? t('lib.tpl.edit') : t('lib.tpl.create')" width="540px">
      <el-form label-width="100px">
        <el-form-item :label="t('common.name')" required>
          <el-input v-model="form.name" :maxlength="100" />
        </el-form-item>
        <el-form-item :label="t('common.description')">
          <el-input v-model="form.description" type="textarea" :rows="3" :maxlength="500" />
        </el-form-item>
        <el-form-item :label="t('building.type')">
          <el-select v-model="form.building_type" style="width: 100%">
            <el-option label="办公" value="office" />
            <el-option label="酒店" value="hotel" />
            <el-option label="商场" value="mall" />
            <el-option label="医院" value="hospital" />
            <el-option label="学校" value="school" />
            <el-option label="住宅" value="residential" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('building.totalArea')">
          <el-input-number v-model="form.total_area" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('building.floors')">
          <el-input-number v-model="form.floor_count" :min="1" style="width: 100%" />
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

    <!-- Clone Dialog -->
    <el-dialog v-model="cloneDlg" :title="t('lib.tpl.useInProject')" width="480px">
      <el-form label-width="100px">
        <el-form-item :label="t('lib.tpl.targetProject')" required>
          <el-select v-model="cloneTargetProject" style="width: 100%" :placeholder="t('lib.tpl.pickProject')">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('common.name')">
          <el-input v-model="cloneNewName" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cloneDlg = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="doClone">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lib-view { padding: 24px 28px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.lib-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.lib-header h1 { margin: 0; font-size: 22px; color: #0f172a; }
.lib-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.tpl-card {
  padding: 16px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(226, 232, 240, 0.6);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.18s;
}
.tpl-card:hover { box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05); }
.tpl-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tpl-name { font-size: 15px; font-weight: 600; color: #0f172a; }
.tpl-meta { display: flex; gap: 10px; font-size: 12px; color: #64748b; }
.tpl-desc {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
}
.tpl-actions { display: flex; gap: 6px; flex-wrap: wrap; padding-top: 6px; border-top: 1px solid rgba(226, 232, 240, 0.5); }
</style>
