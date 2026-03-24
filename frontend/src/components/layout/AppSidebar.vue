<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  HomeFilled,
  OfficeBuilding,
  Setting,
  DataAnalysis,
  Document,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const projectId = computed(() => route.params.projectId as string | undefined)
const buildingId = computed(() => route.params.buildingId as string | undefined)
const resultId = computed(() => route.params.resultId as string | undefined)

// Determine which step is active based on current route
const activeStep = computed(() => {
  if (route.name === 'report') return 4
  if (route.name === 'simulation') return 3
  if (route.name === 'building') return 2
  if (route.name === 'project') return 1
  return 0
})

interface NavStep {
  label: string
  icon: typeof HomeFilled
  path: string | null
  enabled: boolean
}

const steps = computed<NavStep[]>(() => {
  const list: NavStep[] = [
    {
      label: t('nav.projectList'),
      icon: HomeFilled,
      path: '/',
      enabled: true,
    },
  ]

  if (projectId.value) {
    list.push({
      label: t('nav.projectOverview'),
      icon: OfficeBuilding,
      path: `/projects/${projectId.value}`,
      enabled: true,
    })
  }

  if (projectId.value && buildingId.value) {
    list.push({
      label: t('nav.buildingConfig'),
      icon: Setting,
      path: `/projects/${projectId.value}/buildings/${buildingId.value}`,
      enabled: true,
    })
    list.push({
      label: t('nav.simulation'),
      icon: DataAnalysis,
      path: `/projects/${projectId.value}/buildings/${buildingId.value}/simulation`,
      enabled: true,
    })
  }

  if (projectId.value && buildingId.value && resultId.value) {
    list.push({
      label: t('nav.report'),
      icon: Document,
      path: `/projects/${projectId.value}/buildings/${buildingId.value}/report/${resultId.value}`,
      enabled: true,
    })
  }

  return list
})

function onStepClick(step: NavStep) {
  if (step.enabled && step.path) {
    router.push(step.path)
  }
}
</script>

<template>
  <el-aside width="220px" class="app-sidebar">
    <nav class="step-nav">
      <div
        v-for="(step, index) in steps"
        :key="index"
        class="step-item"
        :class="{
          'is-active': index === activeStep,
          'is-done': index < activeStep,
          'is-disabled': !step.enabled,
        }"
        @click="onStepClick(step)"
      >
        <div class="step-indicator">
          <div class="step-line step-line-top" :class="{ invisible: index === 0 }" />
          <div class="step-dot">
            <el-icon :size="16"><component :is="step.icon" /></el-icon>
          </div>
          <div class="step-line step-line-bottom" :class="{ invisible: index >= steps.length - 1 }" />
        </div>
        <span class="step-label">{{ step.label }}</span>
      </div>
    </nav>
  </el-aside>
</template>

<style scoped>
.app-sidebar {
  border-right: 1px solid rgba(226, 232, 240, 0.5);
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  overflow-y: auto;
}

.step-nav {
  padding: 20px 12px;
}

.step-item {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 0 8px;
  transition: all 0.2s;
}

.step-item.is-disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-right: 12px;
  position: relative;
}

.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(241, 245, 249, 0.8);
  color: #94a3b8;
  border: 1.5px solid rgba(226, 232, 240, 0.6);
  transition: all 0.25s ease;
  flex-shrink: 0;
}

.step-line {
  width: 2px;
  height: 14px;
  background: rgba(226, 232, 240, 0.5);
  transition: background 0.2s;
}

.step-line.invisible {
  visibility: hidden;
}

.step-item.is-done .step-dot {
  background: rgba(6, 182, 212, 0.08);
  border-color: rgba(6, 182, 212, 0.3);
  color: #0891b2;
}

.step-item.is-done .step-line {
  background: rgba(6, 182, 212, 0.3);
}

.step-item.is-active .step-dot {
  background: linear-gradient(135deg, #06b6d4, #0284c7);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 2px 8px rgba(6, 182, 212, 0.3);
}

.step-item:not(.is-disabled):hover .step-dot {
  border-color: rgba(6, 182, 212, 0.4);
  color: #0891b2;
  background: rgba(6, 182, 212, 0.06);
}

.step-label {
  font-size: 13px;
  color: #64748b;
  line-height: 32px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s;
  user-select: none;
  min-width: 120px;
  font-weight: 500;
}

.step-item.is-active .step-label {
  color: #0891b2;
  font-weight: 600;
}

.step-item.is-done .step-label {
  color: #334155;
}

.step-item:not(.is-disabled):hover .step-label {
  color: #0891b2;
}
</style>
