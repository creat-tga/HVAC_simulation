<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, Edit, VideoPlay } from '@element-plus/icons-vue'
import { useSimulationStore } from '@/stores/simulation'
import { createHVACSystem, deleteHVACSystem, updateHVACSystem, runSimulation } from '@/api/simulation'
import type { HVACSystemCreate, HVACSystem, SimulationCreate } from '@/types/simulation'
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
  store.fetchResults(buildingId)
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

async function handleRunSimulation() {
  if (store.systems.length === 0) {
    ElMessage.warning(t('system.pleaseAddSystem'))
    return
  }
  const data: SimulationCreate = { simulation_type: 'full_year' }
  await runSimulation(buildingId, data)
  ElMessage.success(t('simulation.taskCreated'))
  store.fetchResults(buildingId)
}

function viewReport(resultId: string) {
  router.push(`/projects/${projectId}/buildings/${buildingId}/report/${resultId}`)
}
</script>

<template>
  <div class="simulation-view">
    <div class="page-header">
      <h1>{{ t('simulation.title') }}</h1>
      <el-button type="success" :icon="VideoPlay" @click="handleRunSimulation">
        {{ t('simulation.run') }}
      </el-button>
    </div>

    <!-- HVAC Systems -->
    <el-card class="section-card">
      <template #header>
        <div class="section-header">
          <span>{{ t('system.title') }}</span>
          <el-button type="primary" :icon="Plus" size="small" @click="openCreateDialog">
            {{ t('system.add') }}
          </el-button>
        </div>
      </template>

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
            <el-button
              type="primary"
              size="small"
              text
              :icon="Edit"
              @click="handleEditSystem(row)"
            />
            <el-button
              type="danger"
              size="small"
              text
              :icon="Delete"
              @click="handleDeleteSystem(row.id)"
            />
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="store.systems.length === 0" :description="t('system.noSystems')" />
    </el-card>

    <!-- Simulation Results -->
    <el-card class="section-card">
      <template #header>
        <span>{{ t('simulation.results') }}</span>
      </template>

      <el-table :data="store.results" stripe>
        <el-table-column prop="simulation_type" :label="t('simulation.type')" width="120" />
        <el-table-column :label="t('simulation.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
              {{ t(`simulation.statusLabels.${row.status}`) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_energy" :label="t('simulation.totalEnergy')" width="140" />
        <el-table-column prop="total_cost" :label="t('simulation.totalCost')" width="140" />
        <el-table-column prop="total_carbon" :label="t('simulation.totalCarbon')" width="140" />
        <el-table-column :label="t('simulation.createdAt')">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column :label="t('common.operation')" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'completed'"
              type="primary"
              size="small"
              text
              @click="viewReport(row.id)"
            >
              {{ t('simulation.viewReport') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="store.results.length === 0" :description="t('simulation.noResults')" />
    </el-card>

    <el-dialog v-model="systemDialogVisible" :title="dialogTitle" width="700px">
      <SystemConfig :key="editingSystem?.id ?? 'new'" :initial-data="editingSystem" @submit="handleCreateSystem" @cancel="systemDialogVisible = false" />
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.section-card {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
