<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useProjectStore()

interface Crumb {
  label: string
  path?: string
}

const breadcrumbs = computed<Crumb[]>(() => {
  const crumbs: Crumb[] = []
  const projectId = route.params.projectId as string | undefined
  const buildingId = route.params.buildingId as string | undefined

  // Always show home
  if (route.name !== 'home') {
    crumbs.push({ label: t('nav.projectList'), path: '/' })
  }

  if (!projectId) return crumbs

  // Project level
  const projectName = store.currentProject?.name
  const projectLabel = projectName || t('nav.projectOverview')
  if (route.name !== 'project') {
    crumbs.push({ label: projectLabel, path: `/projects/${projectId}` })
  } else {
    crumbs.push({ label: projectLabel })
  }

  if (!buildingId) return crumbs

  // Building level
  const building = store.buildings.find(b => b.id === buildingId)
  const buildingLabel = building?.name || t('nav.buildingConfig')

  // Map route names to nav labels
  const routeLabelMap: Record<string, string> = {
    building: t('nav.buildingConfig'),
    loadCalc: t('nav.loadWeather'),
    systemSelect: t('nav.systemSelect'),
    simulation: t('nav.simulation'),
    report: t('nav.report'),
  }

  const currentLabel = routeLabelMap[route.name as string] || ''

  // Building name as intermediate crumb (links to building config)
  if (route.name !== 'building') {
    crumbs.push({ label: buildingLabel, path: `/projects/${projectId}/buildings/${buildingId}` })
  }

  // Current page
  if (currentLabel) {
    crumbs.push({ label: currentLabel })
  }

  return crumbs
})

function navigate(path?: string) {
  if (path) router.push(path)
}
</script>

<template>
  <nav v-if="breadcrumbs.length > 0" class="breadcrumb-nav">
    <template v-for="(crumb, i) in breadcrumbs" :key="i">
      <span v-if="i > 0" class="separator">/</span>
      <span
        class="crumb"
        :class="{ 'is-link': !!crumb.path, 'is-current': !crumb.path }"
        @click="navigate(crumb.path)"
      >
        {{ crumb.label }}
      </span>
    </template>
  </nav>
</template>

<style scoped>
.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px 0;
  font-size: 13px;
  flex-shrink: 0;
}

.separator {
  color: #cbd5e1;
  font-size: 12px;
  user-select: none;
}

.crumb {
  color: #94a3b8;
  transition: color 0.15s;
  user-select: none;
  white-space: nowrap;
}

.crumb.is-link {
  cursor: pointer;
}

.crumb.is-link:hover {
  color: var(--brand-primary);
}

.crumb.is-current {
  color: #1e293b;
  font-weight: 600;
}

@media (max-width: 768px) {
  .breadcrumb-nav {
    padding: 8px 12px 0;
    font-size: 12px;
    overflow-x: auto;
    white-space: nowrap;
  }
}
</style>
