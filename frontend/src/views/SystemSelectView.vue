<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus, Delete, Edit } from '@element-plus/icons-vue'
import { useSimulationStore } from '@/stores/simulation'
import { createHVACSystem, deleteHVACSystem, updateHVACSystem } from '@/api/simulation'
import type { HVACSystemCreate, HVACSystem } from '@/types/simulation'
import SystemConfig from '@/components/simulation/SystemConfig.vue'
import StepNav from '@/components/layout/StepNav.vue'
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
    <!-- Hero header -->
    <div class="page-hero">
      <div class="hero-eyebrow">工程阶段 · 02</div>
      <h1>{{ t('nav.systemSelect') }}</h1>
      <p class="hero-desc">{{ t('simulation.systemStep.description') }}</p>
      <div v-if="store.loadPreviewData" class="load-reference">
        <span class="load-chip load-chip--cool">
          ❄️ {{ t('simulation.loadPreview.peakCooling') }}
          <strong>{{ store.loadPreviewData.peak_cooling_load.toFixed(1) }} kW</strong>
        </span>
        <span class="load-chip load-chip--heat">
          🔥 {{ t('simulation.loadPreview.peakHeating') }}
          <strong>{{ store.loadPreviewData.peak_heating_load.toFixed(1) }} kW</strong>
        </span>
      </div>
    </div>

    <el-card class="system-card" shadow="never">
      <template #header>
        <div class="section-header">
          <div>
            <h3>{{ t('system.title') }}</h3>
            <span class="section-hint">为本建筑配置一个或多个 HVAC 系统方案</span>
          </div>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">
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
            <el-button type="primary" size="small" text :icon="Edit" @click="handleEditSystem(row)" />
            <el-button type="danger" size="small" text :icon="Delete" @click="handleDeleteSystem(row.id)" />
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="store.systems.length === 0" :description="t('system.noSystems')">
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          {{ t('system.add') }}
        </el-button>
      </el-empty>
    </el-card>

    <!-- Navigation -->
    <StepNav
      :prev-label="t('nav.loadWeather')"
      :next-label="t('nav.simulation')"
      :next-disabled="!store.systemConfigured"
      @prev="goBack"
      @next="goToSimulation"
    />

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
.system-select-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Hero header */
.page-hero {
  position: relative;
  overflow: hidden;
  padding: 24px 28px;
  border-radius: 16px;
  background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 50%, #ede9fe 100%);
  border: 1px solid rgba(124, 58, 237, 0.14);
}
.hero-eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7c3aed;
  margin-bottom: 6px;
}
.page-hero h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.hero-desc {
  color: #475569;
  font-size: 14px;
  margin: 0 0 14px;
  line-height: 1.6;
}
.load-reference {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.load-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(124, 58, 237, 0.2);
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  backdrop-filter: blur(6px);
}
.load-chip strong {
  color: #0f172a;
  font-weight: 700;
}
.load-chip--cool { border-color: rgba(8, 145, 178, 0.3); color: #0e7490; }
.load-chip--heat { border-color: rgba(234, 88, 12, 0.3); color: #c2410c; }

/* System list card */
.system-card {
  border-radius: 14px;
  border: 1px solid #e2e8f0;
}
.system-card :deep(.el-card__header) {
  padding: 16px 20px;
  background: #f8fafc;
}
.system-card :deep(.el-card__body) {
  padding: 16px 20px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.section-header h3 {
  margin: 0 0 2px;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}
.section-hint {
  font-size: 13px;
  color: #94a3b8;
}

@media (max-width: 768px) {
  .page-hero h1 { font-size: 20px; }
  .load-reference { flex-direction: column; }
  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
