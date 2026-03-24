<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, Edit, Search, CopyDocument } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import type { ProjectCreate, ProjectUpdate, Project } from '@/types/project'
import { createProject, deleteProject, updateProject, batchDeleteProjects, copyProject } from '@/api/projects'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { CascaderValue, FormRules, FormInstance } from 'element-plus'
import { regionData } from '@/data/regions'

const NAME_MAX = 30
const DESC_MAX = 1500

const router = useRouter()
const store = useProjectStore()
const { t } = useI18n()

// Filter state
const searchKeyword = ref('')
const sortOrder = ref<'newest' | 'oldest'>('newest')

// Batch selection
const batchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const lastSelectedIndex = ref(-1)

function toggleBatchMode() {
  batchMode.value = !batchMode.value
  selectedIds.value.clear()
  lastSelectedIndex.value = -1
}

function toggleSelect(id: string, event?: MouseEvent) {
  const list = filteredProjects.value
  const currentIndex = list.findIndex(p => p.id === id)

  if (event?.shiftKey && lastSelectedIndex.value >= 0 && currentIndex >= 0) {
    const start = Math.min(lastSelectedIndex.value, currentIndex)
    const end = Math.max(lastSelectedIndex.value, currentIndex)
    // Toggle: if anchor is selected → select range, if not → deselect range
    const shouldSelect = !selectedIds.value.has(id)
    for (let i = start; i <= end; i++) {
      if (shouldSelect) {
        selectedIds.value.add(list[i].id)
      } else {
        selectedIds.value.delete(list[i].id)
      }
    }
  } else {
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id)
    } else {
      selectedIds.value.add(id)
    }
  }

  if (currentIndex >= 0) {
    lastSelectedIndex.value = currentIndex
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.size === 0) return
  await ElMessageBox.confirm(
    t('project.batchDeleteConfirm', { count: selectedIds.value.size }),
    t('common.warning'),
    { type: 'warning' }
  )
  await batchDeleteProjects([...selectedIds.value])
  ElMessage.success(t('project.batchDeleteSuccess', { count: selectedIds.value.size }))
  selectedIds.value.clear()
  batchMode.value = false
  store.fetchProjects()
}

async function handleCopy(id: string, event: Event) {
  event.stopPropagation()
  await copyProject(id)
  ElMessage.success(t('project.copySuccess'))
  store.fetchProjects()
}

// Tooltip overflow detection
const descOverflow = reactive<Record<string, boolean>>({})

function checkDescOverflow(id: string, event: MouseEvent) {
  const card = event.currentTarget as HTMLElement
  const desc = card.querySelector('.description') as HTMLElement
  if (desc) {
    descOverflow[id] = desc.scrollHeight > desc.clientHeight + 1
  }
}

const filteredProjects = computed(() => {
  let list = [...store.projects]
  const kw = searchKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter(p =>
      p.name.toLowerCase().includes(kw) ||
      (p.location && p.location.toLowerCase().includes(kw))
    )
  }
  list.sort((a, b) => {
    const ta = new Date(a.created_at).getTime()
    const tb = new Date(b.created_at).getTime()
    return sortOrder.value === 'newest' ? tb - ta : ta - tb
  })
  return list
})

const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref('')
const formRef = ref<FormInstance>()
const form = ref<ProjectCreate>({ name: '', description: '', location: '' })
const locationValue = ref<string[]>([])

const rules: FormRules = {
  name: [
    { required: true, message: () => t('project.pleaseInputName'), trigger: 'blur' },
    { max: NAME_MAX, message: () => t('project.nameMaxLength', { max: NAME_MAX }), trigger: 'change' },
  ],
  description: [
    { max: DESC_MAX, message: () => t('project.descMaxLength', { max: DESC_MAX }), trigger: 'change' },
  ],
  location: [
    { required: true, message: () => t('project.pleaseSelectLocation'), trigger: 'change' },
  ],
}

onMounted(() => {
  store.fetchProjects()
})

function onLocationChange(val: CascaderValue | null | undefined) {
  const arr = val as string[] | null
  if (arr && arr.length >= 2) {
    form.value.location = `${arr[0]}-${arr[1]}`
  } else if (arr && arr.length === 1) {
    form.value.location = arr[0]
  } else {
    form.value.location = ''
  }
}

function openCreateDialog() {
  isEditing.value = false
  editingId.value = ''
  form.value = { name: '', description: '', location: '' }
  locationValue.value = []
  dialogVisible.value = true
}

function openEditDialog(project: Project, event: Event) {
  event.stopPropagation()
  isEditing.value = true
  editingId.value = project.id
  form.value = {
    name: project.name,
    description: project.description || '',
    location: project.location || '',
  }
  locationValue.value = project.location ? project.location.split('-') : []
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (isEditing.value) {
    const data: ProjectUpdate = {
      name: form.value.name,
      description: form.value.description,
      location: form.value.location,
    }
    await updateProject(editingId.value, data)
    ElMessage.success(t('project.updateSuccess'))
  } else {
    await createProject(form.value)
    ElMessage.success(t('project.createSuccess'))
  }
  dialogVisible.value = false
  form.value = { name: '', description: '', location: '' }
  locationValue.value = []
  store.fetchProjects()
}

async function handleDelete(id: string) {
  await ElMessageBox.confirm(t('project.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteProject(id)
  ElMessage.success(t('project.deleteSuccess'))
  store.fetchProjects()
}

function openProject(id: string) {
  router.push(`/projects/${id}`)
}
</script>

<template>
  <div class="home-view">
    <div class="fixed-top">
    <div class="page-header">
      <h1>{{ t('project.title') }}</h1>
      <div class="header-actions">
        <el-button v-if="batchMode" type="danger" :icon="Delete" :disabled="selectedIds.size === 0" @click="handleBatchDelete">
          {{ t('project.batchDelete') }} ({{ selectedIds.size }})
        </el-button>
        <el-button :type="batchMode ? 'info' : 'default'" plain @click="toggleBatchMode">
          {{ batchMode ? t('common.cancel') : t('project.batchSelect') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          {{ t('project.create') }}
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        :prefix-icon="Search"
        :placeholder="t('project.searchPlaceholder')"
        clearable
        style="width: 280px"
      />
      <el-select v-model="sortOrder" style="width: 150px">
        <el-option :label="t('project.sortNewest')" value="newest" />
        <el-option :label="t('project.sortOldest')" value="oldest" />
      </el-select>
    </div>
    </div>

    <div class="scroll-area">
    <el-row :gutter="20" v-loading="store.loading">
      <el-col
        v-for="project in filteredProjects"
        :key="project.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <el-card
          class="project-card"
          :class="{ 'is-selected': batchMode && selectedIds.has(project.id) }"
          @click="batchMode ? toggleSelect(project.id, $event as MouseEvent) : openProject(project.id)"
          @mouseenter="checkDescOverflow(project.id, $event)"
        >
          <div class="card-body">
            <div class="card-top">
              <el-checkbox
                v-if="batchMode"
                :model-value="selectedIds.has(project.id)"
                @click.stop="toggleSelect(project.id, $event as MouseEvent)"
                style="margin-right: 8px"
              />
              <span class="card-title" :title="project.name">{{ project.name }}</span>
              <div class="card-actions" v-if="!batchMode">
                <el-button
                  :icon="CopyDocument"
                  size="small"
                  text
                  @click="handleCopy(project.id, $event)"
                />
                <el-button
                  type="primary"
                  :icon="Edit"
                  size="small"
                  text
                  @click="openEditDialog(project, $event)"
                />
                <el-button
                  type="danger"
                  :icon="Delete"
                  size="small"
                  text
                  @click.stop="handleDelete(project.id)"
                />
              </div>
            </div>
            <el-tooltip
              :content="project.description || ''"
              placement="top"
              :disabled="!descOverflow[project.id]"
              effect="light"
              :show-after="300"
              :popper-style="{ maxWidth: '1000px', lineHeight: '1.6', padding: '10px 14px' }"
            >
              <p class="description">{{ project.description || t('project.noDescription') }}</p>
            </el-tooltip>
            <div class="card-footer">
              <el-tag v-if="project.location" size="small" effect="plain">{{ project.location }}</el-tag>
              <span v-else />
              <span class="date">{{ new Date(project.created_at).toLocaleDateString() }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!store.loading && filteredProjects.length === 0" :description="searchKeyword ? t('project.noSearchResults') : t('project.noProjects')" />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? t('project.editProject') : t('project.create')"
      width="520px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item :label="t('project.name')" prop="name" required>
          <el-input
            v-model="form.name"
            :maxlength="NAME_MAX"
            show-word-limit
            :placeholder="t('project.pleaseInputName')"
          />
        </el-form-item>
        <el-form-item :label="t('project.description')" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            :maxlength="DESC_MAX"
            show-word-limit
            :placeholder="t('project.pleaseInputDesc')"
          />
        </el-form-item>
        <el-form-item :label="t('project.location')" prop="location" required>
          <el-cascader
            v-model="locationValue"
            :options="(regionData as any)"
            :placeholder="t('project.pleaseSelectLocation')"
            filterable
            style="width: 100%"
            @change="onLocationChange"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSubmit">
          {{ isEditing ? t('common.save') : t('common.create') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.home-view {
  padding: 4px;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.fixed-top {
  flex-shrink: 0;
}

.scroll-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-top: 6px;
  padding-right: 4px;
  user-select: none;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: center;
}

.project-card {
  margin-bottom: 20px;
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
  height: 170px;
}

.project-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(6, 182, 212, 0.08) !important;
  border-color: rgba(6, 182, 212, 0.25) !important;
}

.project-card.is-selected {
  border-color: #0891b2 !important;
  box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.15) !important;
}

.project-card :deep(.el-card__body) {
  padding: 16px 20px;
  height: 100%;
  box-sizing: border-box;
}

.card-body {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  letter-spacing: -0.01em;
}

.card-actions {
  flex-shrink: 0;
  margin-left: 8px;
}

.description {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  height: 42px;
  flex-shrink: 0;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid rgba(226, 232, 240, 0.5);
}

.date {
  color: #94a3b8;
  font-size: 12px;
}
</style>
