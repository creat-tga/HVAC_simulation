/**
 * Equipment library cache.
 *
 * Holds the full list of public equipment per type so the picker can do
 * client-side filtering without re-hitting the backend on every dropdown
 * open. Backed by `searchEquipment` (no filters → entire typed table).
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { searchEquipment } from '@/api/system-scheme'
import type { EquipmentBrief, EquipmentSearchParams } from '@/types/system-scheme'

type EqType = EquipmentSearchParams['equipment_type']

export const useEquipmentLibraryStore = defineStore('equipmentLibrary', () => {
  const cache = ref<Record<string, EquipmentBrief[]>>({})
  const loading = ref<Record<string, boolean>>({})
  const inflight = new Map<string, Promise<EquipmentBrief[]>>()

  async function load(type: EqType, force = false): Promise<EquipmentBrief[]> {
    if (!force && cache.value[type]) return cache.value[type]
    const existing = inflight.get(type)
    if (existing) return existing

    loading.value[type] = true
    const promise = (async () => {
      try {
        const { data } = await searchEquipment({ equipment_type: type })
        cache.value[type] = data || []
        return cache.value[type]
      } finally {
        loading.value[type] = false
        inflight.delete(type)
      }
    })()
    inflight.set(type, promise)
    return promise
  }

  function get(type: EqType): EquipmentBrief[] {
    return cache.value[type] || []
  }

  function isLoading(type: EqType): boolean {
    return !!loading.value[type]
  }

  function findById(id: string): EquipmentBrief | undefined {
    for (const list of Object.values(cache.value)) {
      const hit = list.find((e) => e.id === id)
      if (hit) return hit
    }
    return undefined
  }

  function invalidate(type?: EqType) {
    if (type) {
      delete cache.value[type]
    } else {
      cache.value = {}
    }
  }

  return { cache, loading, load, get, isLoading, findById, invalidate }
})
