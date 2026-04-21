<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'
import { getSimulations } from '@/api/simulation'
import { Setting, Right } from '@element-plus/icons-vue'
import type { Building } from '@/types/building'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useProjectStore()
const projectId = route.params.projectId as string

const loadStatus = reactive<Record<string, boolean>>({})
const loading = ref(false)

async function loadAll() {
  loading.value = true
  try {
    if (store.buildings.length === 0) await store.fetchBuildings(projectId)
    for (const b of store.buildings) {
      try {
        const { data } = await getSimulations(b.id)
        loadStatus[b.id] = data.some(r => r.status === 'completed' && r.simulation_type === 'load')
      } catch {
        loadStatus[b.id] = false
      }
    }
  } finally {
    loading.value = false
  }
}

function goSystem(b: Building) {
  if (!loadStatus[b.id]) return
  router.push(`/projects/${projectId}/buildings/${b.id}/system`)
}

onMounted(loadAll)
</script>

<template>
  <div class="ws-page">
    <div class="ws-page-header">
      <h2>{{ t('workspace.system') }}</h2>
      <p>{{ t('workspace.systemHint') }}</p>
    </div>

    <el-empty
      v-if="!loading && store.buildings.length === 0"
      :description="t('workspace.noBuildings')"
    >
      <el-button type="primary" @click="router.push(`/projects/${projectId}/building`)">
        {{ t('workspace.gotoBuilding') }}
      </el-button>
    </el-empty>

    <div v-else class="building-grid" v-loading="loading">
      <div
        v-for="b in store.buildings"
        :key="b.id"
        class="building-row"
        :class="{ disabled: !loadStatus[b.id] }"
        @click="goSystem(b)"
      >
        <div class="left">
          <el-icon :size="22" class="icon"><Setting /></el-icon>
          <div>
            <div class="name">{{ b.name }}</div>
            <div class="meta">
              <el-tag v-if="loadStatus[b.id]" size="small" type="success">{{ t('workspace.loadDone') }}</el-tag>
              <el-tag v-else size="small" type="warning">{{ t('workspace.loadPending') }}</el-tag>
              <span v-if="b.building_type">{{ t(`building.types.${b.building_type}`) }}</span>
            </div>
          </div>
        </div>
        <el-icon :size="18" class="arrow"><Right /></el-icon>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ws-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}
.ws-page-header {
  margin-bottom: 20px;
}
.ws-page-header h2 {
  margin: 0 0 6px 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ws-page-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
.building-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.building-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(226, 232, 240, 0.6);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.building-row:hover {
  border-color: #0891b2;
  transform: translateY(-2px);
  box-shadow: 0 8px 18px rgba(8, 145, 178, 0.10);
}
.building-row.disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.building-row.disabled:hover {
  transform: none;
  border-color: rgba(226, 232, 240, 0.6);
  box-shadow: none;
}
.left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.icon {
  color: #0891b2;
}
.name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.arrow {
  color: #cbd5e1;
}
</style>
