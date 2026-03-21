import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { HVACSystem, SimulationResult } from '@/types/simulation'
import { getHVACSystems, getSimulations } from '@/api/simulation'

export const useSimulationStore = defineStore('simulation', () => {
  const systems = ref<HVACSystem[]>([])
  const results = ref<SimulationResult[]>([])
  const loading = ref(false)

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

  return {
    systems,
    results,
    loading,
    fetchSystems,
    fetchResults,
  }
})
