<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { getProject } from '@/api/projects'
import { createBuilding, deleteBuilding } from '@/api/buildings'
import BuildingForm from '@/components/building/BuildingForm.vue'
import type { BuildingCreate } from '@/types/building'
import type { Project } from '@/types/project'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getClimateZone } from '@/data/regions'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const { t } = useI18n()

const project = ref<Project | null>(null)
const dialogVisible = ref(false)
const projectId = route.params.projectId as string

// Description overflow detection
const descRef = ref<HTMLElement>()
const descOverflow = ref(false)

function checkDescOverflow() {
  if (descRef.value) {
    descOverflow.value = descRef.value.scrollHeight > descRef.value.clientHeight + 1
  }
}

onMounted(async () => {
  const { data } = await getProject(projectId)
  project.value = data
  store.setCurrentProject(data)
  store.fetchBuildings(projectId)
})

async function handleCreateBuilding(data: BuildingCreate) {
  if (project.value?.location) {
    const province = project.value.location.split('-')[0]
    data.climate_zone = getClimateZone(province)
  }
  await createBuilding(projectId, data)
  ElMessage.success(t('building.createSuccess'))
  dialogVisible.value = false
  store.fetchBuildings(projectId)
}

async function handleDeleteBuilding(buildingId: string) {
  await ElMessageBox.confirm(t('building.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteBuilding(projectId, buildingId)
  ElMessage.success(t('building.deleteSuccess'))
  store.fetchBuildings(projectId)
}

function openBuilding(buildingId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}`)
}
</script>

<template>
  <div class="project-view">
    <div class="page-header">
      <div>
        <h1>{{ project?.name }}</h1>
        <el-tooltip
          :content="project?.description || ''"
          placement="bottom"
          :disabled="!descOverflow"
          effect="light"
          :show-after="300"
          :popper-style="{ maxWidth: '1200px', lineHeight: '1.6', padding: '12px 16px' }"
        >
          <p ref="descRef" class="description" @mouseenter="checkDescOverflow">{{ project?.description || t('project.noDescription') }}</p>
        </el-tooltip>
        <el-tag v-if="project?.location" type="info" style="margin-top: 8px">
          📍 {{ project.location }}
        </el-tag>
      </div>
    </div>

    <el-divider />

    <div class="section-header">
      <h2>{{ t('building.title') }}</h2>
      <el-button type="primary" :icon="Plus" @click="dialogVisible = true">
        {{ t('building.add') }}
      </el-button>
    </div>

    <el-table :data="store.buildings" v-loading="store.loading" stripe>
      <el-table-column prop="name" :label="t('building.name')" />
      <el-table-column :label="t('building.type')" width="120">
        <template #default="{ row }">
          {{ t(`building.types.${row.building_type}`) }}
        </template>
      </el-table-column>
      <el-table-column prop="total_area" :label="t('building.area')" width="120" />
      <el-table-column prop="floor_count" :label="t('building.floors')" width="100" />
      <el-table-column :label="t('building.climateZone')" width="120">
        <template #default="{ row }">
          {{ row.climate_zone ? t(`building.climateZones.${row.climate_zone}`) : '-' }}
        </template>
      </el-table-column>
      <el-table-column :label="t('common.operation')" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" text @click="openBuilding(row.id)">
            {{ t('building.config') }}
          </el-button>
          <el-button
            type="danger"
            size="small"
            text
            :icon="Delete"
            @click="handleDeleteBuilding(row.id)"
          >
            {{ t('common.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!store.loading && store.buildings.length === 0" :description="t('building.noBuildings')" />

    <el-dialog v-model="dialogVisible" :title="t('building.add')" width="600px">
      <BuildingForm @submit="handleCreateBuilding" @cancel="dialogVisible = false" />
    </el-dialog>


  </div>
</template>

<style scoped>
.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
}

.description {
  color: var(--el-text-color-secondary);
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  max-height: 45px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h2 {
  margin: 0;
}
</style>
