import api from '@/api'
import type {
  WeatherFile,
  EquipmentModel,
  EquipmentModelCreate,
  BuildingTemplate,
  BuildingTemplateCreate,
} from '@/types/library'
import type { Building } from '@/types/building'

// ---- Weather ----
export function listWeatherFiles(search?: string) {
  return api.get<WeatherFile[]>('/weather/files', { params: { search } })
}

export function uploadWeatherFile(file: File, meta: { name?: string; province?: string; city?: string } = {}) {
  const fd = new FormData()
  fd.append('file', file)
  if (meta.name) fd.append('name', meta.name)
  if (meta.province) fd.append('province', meta.province)
  if (meta.city) fd.append('city', meta.city)
  return api.post<WeatherFile>('/weather/files', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteWeatherFile(id: string) {
  return api.delete(`/weather/files/${id}`)
}

// ---- Equipment ----
export function listEquipment(params: { equipment_type?: string; scope?: 'all' | 'public' | 'mine' } = {}) {
  return api.get<EquipmentModel[]>('/equipment', { params })
}

export function createEquipment(data: EquipmentModelCreate) {
  return api.post<EquipmentModel>('/equipment', data)
}

export function updateEquipment(id: string, data: Partial<EquipmentModelCreate>) {
  return api.patch<EquipmentModel>(`/equipment/${id}`, data)
}

export function deleteEquipment(id: string) {
  return api.delete(`/equipment/${id}`)
}

// ---- Building Templates ----
export function listBuildingTemplates(scope: 'all' | 'public' | 'mine' = 'all') {
  return api.get<BuildingTemplate[]>('/templates/buildings', { params: { scope } })
}

export function createBuildingTemplate(data: BuildingTemplateCreate) {
  return api.post<BuildingTemplate>('/templates/buildings', data)
}

export function updateBuildingTemplate(id: string, data: Partial<BuildingTemplateCreate>) {
  return api.patch<BuildingTemplate>(`/templates/buildings/${id}`, data)
}

export function deleteBuildingTemplate(id: string) {
  return api.delete(`/templates/buildings/${id}`)
}

export function cloneTemplateToProject(templateId: string, projectId: string, name?: string) {
  return api.post<Building>(`/templates/buildings/${templateId}/clone-to-project`, {
    project_id: projectId,
    name,
  })
}

export function cloneBuildingToTemplate(
  buildingId: string,
  data: { name?: string; description?: string; is_public?: boolean } = {},
) {
  return api.post<BuildingTemplate>(`/templates/buildings/from-building/${buildingId}`, data)
}
