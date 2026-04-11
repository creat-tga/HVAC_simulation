import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { HVACSystem, SimulationResult, LoadPreview } from '@/types/simulation'
import { getHVACSystems, getSimulations } from '@/api/simulation'

export const useSimulationStore = defineStore('simulation', () => {
  const systems = ref<HVACSystem[]>([])
  const results = ref<SimulationResult[]>([])
  const loadResults = ref<SimulationResult[]>([])
  const energyResults = ref<SimulationResult[]>([])
  const loading = ref(false)
  const loadPreviewData = ref<LoadPreview | null>(null)

  const loadCompleted = computed(() => {
    // Check if there's a completed load simulation
    return loadResults.value.some(r => r.status === 'completed') || loadPreviewData.value !== null
  })

  const latestLoadResult = computed(() => {
    return loadResults.value.find(r => r.status === 'completed') || null
  })

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

  async function fetchLoadResults(buildingId: string) {
    try {
      const { data } = await getSimulations(buildingId, 'load')
      loadResults.value = data
    } catch {
      // ignore
    }
  }

  async function fetchEnergyResults(buildingId: string) {
    try {
      const { data } = await getSimulations(buildingId, 'energy')
      energyResults.value = data
    } catch {
      // ignore
    }
  }

  function setLoadPreview(data: LoadPreview) {
    loadPreviewData.value = data
  }

  function $reset() {
    systems.value = []
    results.value = []
    loadResults.value = []
    energyResults.value = []
    loading.value = false
    loadPreviewData.value = null
  }

  return {
    systems,
    results,
    loadResults,
    energyResults,
    loading,
    loadPreviewData,
    loadCompleted,
    latestLoadResult,
    systemConfigured,
    fetchSystems,
    fetchResults,
    fetchLoadResults,
    fetchEnergyResults,
    setLoadPreview,
    $reset,
  }
})
