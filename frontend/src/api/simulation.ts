import api from '@/api'
import type {
  HVACSystem,
  HVACSystemCreate,
  HVACSystemUpdate,
  SimulationResult,
  SimulationDetail,
  SimulationCreate,
} from '@/types/simulation'

// HVAC Systems
export function getHVACSystems(buildingId: string) {
  return api.get<HVACSystem[]>(`/buildings/${buildingId}/systems`)
}

export function createHVACSystem(buildingId: string, data: HVACSystemCreate) {
  return api.post<HVACSystem>(`/buildings/${buildingId}/systems`, data)
}

export function updateHVACSystem(buildingId: string, systemId: string, data: HVACSystemUpdate) {
  return api.put<HVACSystem>(`/buildings/${buildingId}/systems/${systemId}`, data)
}

export function deleteHVACSystem(buildingId: string, systemId: string) {
  return api.delete(`/buildings/${buildingId}/systems/${systemId}`)
}

// Simulations
export function getSimulations(buildingId: string) {
  return api.get<SimulationResult[]>(`/buildings/${buildingId}/simulations`)
}

export function runSimulation(buildingId: string, data: SimulationCreate) {
  return api.post<SimulationResult>(`/buildings/${buildingId}/simulations`, data)
}

export function getSimulationDetail(buildingId: string, resultId: string) {
  return api.get<SimulationDetail>(`/buildings/${buildingId}/simulations/${resultId}`)
}
