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
  border-right: 1px solid #e8e8e8;
  background: #fff;
  overflow-y: auto;
}

.step-nav {
  padding: 20px 16px;
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
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  border: 2px solid var(--el-border-color);
  transition: all 0.2s;
  flex-shrink: 0;
}

.step-line {
  width: 2px;
  height: 16px;
  background: var(--el-border-color);
  transition: background 0.2s;
}

.step-line.invisible {
  visibility: hidden;
}

.step-item.is-done .step-dot {
  background: var(--el-color-primary-light-7);
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.step-item.is-done .step-line {
  background: var(--el-color-primary);
}

.step-item.is-active .step-dot {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
  box-shadow: 0 0 0 4px var(--el-color-primary-light-7);
}

.step-item:not(.is-disabled):hover .step-dot {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.step-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 32px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s;
  user-select: none;
  min-width: 120px;
}


.step-item.is-active .step-label {
  color: var(--el-color-primary);
  font-weight: 500;
}

.step-item.is-done .step-label {
  color: var(--el-text-color-primary);
}

.step-item:not(.is-disabled):hover .step-label {
  color: var(--el-color-primary);
}
</style>
