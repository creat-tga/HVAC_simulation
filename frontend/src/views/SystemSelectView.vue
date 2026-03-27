<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, Edit } from '@element-plus/icons-vue'
import { useSimulationStore } from '@/stores/simulation'
import { createHVACSystem, deleteHVACSystem, updateHVACSystem } from '@/api/simulation'
import type { HVACSystemCreate, HVACSystem } from '@/types/simulation'
import SystemConfig from '@/components/simulation/SystemConfig.vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useSimulationStore()

const buildingId = route.params.buildingId as string
const projectId = route.params.projectId as string

const systemDialogVisible = ref(false)
const editingSystem = ref<HVACSystem | null>(null)
const dialogTitle = computed(() => editingSystem.value ? t('system.editSystem') : t('system.add'))

onMounted(() => {
  store.fetchSystems(buildingId)
})

function getSystemLabel(type: string) {
  return t(`system.types.${type}`, type)
}

async function handleCreateSystem(data: HVACSystemCreate) {
  if (editingSystem.value) {
    await updateHVACSystem(buildingId, editingSystem.value.id, data)
    ElMessage.success(t('system.updateSuccess'))
  } else {
    await createHVACSystem(buildingId, data)
    ElMessage.success(t('system.createSuccess'))
  }
  systemDialogVisible.value = false
  editingSystem.value = null
  store.fetchSystems(buildingId)
}

function handleEditSystem(system: HVACSystem) {
  editingSystem.value = system
  systemDialogVisible.value = true
}

function openCreateDialog() {
  editingSystem.value = null
  systemDialogVisible.value = true
}

async function handleDeleteSystem(systemId: string) {
  await ElMessageBox.confirm(t('system.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteHVACSystem(buildingId, systemId)
  ElMessage.success(t('system.deleteSuccess'))
  store.fetchSystems(buildingId)
}

function goToSimulation() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/simulation`)
}

function goBack() {
  router.push(`/projects/${projectId}/buildings/${buildingId}/load`)
}
</script>

<template>
  <div class="system-select-view">
    <div class="page-header">
      <h1>{{ t('simulation.steps.systemConfig') }}</h1>
    </div>

    <el-card>
      <div class="step-desc">
        <p>{{ t('simulation.systemStep.description') }}</p>
        <div v-if="store.loadPreviewData" class="load-reference">
          <el-tag type="info" effect="plain">
            {{ t('simulation.loadPreview.peakCooling') }}: {{ store.loadPreviewData.peak_cooling_load.toFixed(1) }} kW
          </el-tag>
          <el-tag type="warning" effect="plain">
            {{ t('simulation.loadPreview.peakHeating') }}: {{ store.loadPreviewData.peak_heating_load.toFixed(1) }} kW
          </el-tag>
        </div>
      </div>

      <div class="section-header">
        <h3>{{ t('system.title') }}</h3>
        <el-button type="primary" :icon="Plus" size="small" @click="openCreateDialog">
          {{ t('system.add') }}
        </el-button>
      </div>

      <el-table :data="store.systems" v-loading="store.loading" stripe>
        <el-table-column prop="name" :label="t('system.name')" />
        <el-table-column :label="t('system.type')" width="150">
          <template #default="{ row }">
            <el-tag>{{ getSystemLabel(row.system_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="capacity" :label="t('system.capacity')" width="120" />
        <el-table-column prop="cop" label="COP" width="100" />
        <el-table-column :label="t('common.operation')" width="120">
          <template #default="{ row }">
            <el-button type="primary" size="small" text :icon="Edit" @click="handleEditSystem(row)" />
            <el-button type="danger" size="small" text :icon="Delete" @click="handleDeleteSystem(row.id)" />
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="store.systems.length === 0" :description="t('system.noSystems')" />
    </el-card>

    <!-- Navigation -->
    <div class="nav-buttons">
      <el-button @click="goBack">← {{ t('simulation.steps.loadSimulation') }}</el-button>
      <el-button
        type="primary"
        :disabled="!store.systemConfigured"
        @click="goToSimulation"
      >
        {{ t('simulation.steps.energySimulation') }} →
      </el-button>
    </div>

    <el-dialog v-model="systemDialogVisible" :title="dialogTitle" width="700px">
      <SystemConfig
        :key="editingSystem?.id ?? 'new'"
        :initial-data="editingSystem"
        @submit="handleCreateSystem"
        @cancel="systemDialogVisible = false"
      />
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.step-desc {
  margin-bottom: 20px;
}

.step-desc p {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.load-reference {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.nav-buttons {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
}
</style>
