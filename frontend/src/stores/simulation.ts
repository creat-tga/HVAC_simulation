import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { HVACSystem, SimulationResult, LoadPreview } from '@/types/simulation'
import { getHVACSystems, getSimulations } from '@/api/simulation'

export const useSimulationStore = defineStore('simulation', () => {
  const systems = ref<HVACSystem[]>([])
  const results = ref<SimulationResult[]>([])
  const loading = ref(false)
  const loadPreviewData = ref<LoadPreview | null>(null)

  const loadCompleted = computed(() => loadPreviewData.value !== null)
  const systemConfigured = computed(() => systems.value.length > 0)

  async function fetchSystems(buildingId: string) {
    loading.value = true
    try {
      const { data } = await getHVACSystems(buildingId)
      systems.value = data
    } finally {
      loading.value = false
    }
  }

  async function fetchResults(buildingId: string) {
    loading.value = true
    try {
      const { data } = await getSimulations(buildingId)
      results.value = data
    } finally {
      loading.value = false
    }
  }

  function setLoadPreview(data: LoadPreview) {
    loadPreviewData.value = data
  }

  function $reset() {
    systems.value = []
    results.value = []
    loading.value = false
    loadPreviewData.value = null
  }

  return {
    systems,
    results,
    loading,
    loadPreviewData,
    loadCompleted,
    systemConfigured,
    fetchSystems,
    fetchResults,
    setLoadPreview,
    $reset,
  }
})
