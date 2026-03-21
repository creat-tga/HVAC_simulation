import api from '@/api'
import type { Project, ProjectCreate, ProjectUpdate } from '@/types/project'

export function getProjects() {
  return api.get<Project[]>('/projects/')
}

export function getProject(id: string) {
  return api.get<Project>(`/projects/${id}`)
}

export function createProject(data: ProjectCreate) {
  return api.post<Project>('/projects/', data)
}

export function updateProject(id: string, data: ProjectUpdate) {
  return api.put<Project>(`/projects/${id}`, data)
}

export function deleteProject(id: string) {
  return api.delete(`/projects/${id}`)
}

export function batchDeleteProjects(ids: string[]) {
  return api.post<{ deleted: number }>('/projects/batch-delete', { ids })
}

export function copyProject(id: string) {
  return api.post<Project>(`/projects/${id}/copy`)
}
