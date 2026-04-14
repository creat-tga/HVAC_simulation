import api from '@/api'
import type {
  HVACSystem,
  HVACSystemCreate,
  HVACSystemUpdate,
  SimulationResult,
  SimulationDetail,
  SimulationStatus,
} from '@/types/simulation'

// Load Simulation (background task)
export function runLoadSimulation(buildingId: string) {
  return api.post<SimulationResult>(`/buildings/${buildingId}/load-simulation`)
}

// Energy Simulation (uses existing load results)
export function runEnergySimulation(buildingId: string, loadResultId: string) {
  return api.post<SimulationResult>(`/buildings/${buildingId}/energy-simulation`, {
    simulation_type: 'energy',
    load_result_id: loadResultId,
  })
}

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
export function getSimulations(buildingId: string, simulationType?: string) {
  const params = simulationType ? { simulation_type: simulationType } : {}
  return api.get<SimulationResult[]>(`/buildings/${buildingId}/simulations`, { params })
}

export function getSimulationDetail(buildingId: string, resultId: string) {
  return api.get<SimulationDetail>(`/buildings/${buildingId}/simulations/${resultId}`)
}

export function getSimulationStatus(buildingId: string, resultId: string) {
  return api.get<SimulationStatus>(`/buildings/${buildingId}/simulations/${resultId}/status`)
}

export function cancelSimulation(buildingId: string, resultId: string) {
  return api.post<SimulationStatus>(`/buildings/${buildingId}/simulations/${resultId}/cancel`)
}

export function getWeatherData(buildingId: string) {
  return api.get<{
    dry_bulb_temperature: number[]
    dew_point_temperature: number[]
    relative_humidity: number[]
    location: { name: string; lat: number; lon: number; elev: number }
  }>(`/buildings/${buildingId}/weather-data`)
}
