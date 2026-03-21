import api from '@/api'
import type { Building, BuildingCreate, BuildingUpdate } from '@/types/building'

export function getBuildings(projectId: string) {
  return api.get<Building[]>(`/projects/${projectId}/buildings/`)
}

export function getBuilding(projectId: string, buildingId: string) {
  return api.get<Building>(`/projects/${projectId}/buildings/${buildingId}`)
}

export function createBuilding(projectId: string, data: BuildingCreate) {
  return api.post<Building>(`/projects/${projectId}/buildings/`, data)
}

export function updateBuilding(projectId: string, buildingId: string, data: BuildingUpdate) {
  return api.put<Building>(`/projects/${projectId}/buildings/${buildingId}`, data)
}

export function deleteBuilding(projectId: string, buildingId: string) {
  return api.delete(`/projects/${projectId}/buildings/${buildingId}`)
}
