<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useSimulationStore } from '@/stores/simulation'

const route = useRoute()
const projectStore = useProjectStore()
const simulationStore = useSimulationStore()

// Ensure building data is loaded when entering building context
watch(
  () => route.params.buildingId as string | undefined,
  (buildingId) => {
    if (buildingId) {
      simulationStore.fetchSystems(buildingId)
    }
  },
  { immediate: true },
)

watch(
  () => route.params.projectId as string | undefined,
  (projectId) => {
    if (projectId && projectStore.buildings.length === 0) {
      projectStore.fetchBuildings(projectId)
    }
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
</template>
