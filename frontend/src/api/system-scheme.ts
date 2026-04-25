import api from '@/api'
import type {
  CapacitySummary,
  EquipmentBrief,
  EquipmentSearchParams,
  SchemeDerived,
  SystemScheme,
  SystemSchemeCreate,
  SystemSchemeListItem,
  SystemSchemeUpdate,
  ValidationReport,
} from '@/types/system-scheme'

const projBase = (projectId: string) => `/projects/${projectId}/system-schemes`
const schBase = (schemeId: string) => `/system-schemes/${schemeId}`

// ---- project-level ----

export function listSchemes(projectId: string) {
  return api.get<SystemSchemeListItem[]>(projBase(projectId))
}

export function createScheme(projectId: string, data: SystemSchemeCreate) {
  return api.post<SystemScheme>(projBase(projectId), data)
}

export function validateProjectSchemes(projectId: string) {
  return api.post<ValidationReport>(`${projBase(projectId)}/validate`)
}

// ---- single scheme ----

export function getScheme(schemeId: string) {
  return api.get<SystemScheme>(schBase(schemeId))
}

export function updateScheme(schemeId: string, data: SystemSchemeUpdate) {
  return api.put<SystemScheme>(schBase(schemeId), data)
}

export function deleteScheme(schemeId: string) {
  return api.delete(schBase(schemeId))
}

export function getSchemeSummary(schemeId: string) {
  return api.get<CapacitySummary>(`${schBase(schemeId)}/summary`)
}

export function getSchemeDerived(schemeId: string) {
  return api.get<SchemeDerived>(`${schBase(schemeId)}/derived`)
}

export interface SchemeBundle {
  scheme: SystemScheme
  derived: SchemeDerived
  summary: CapacitySummary
}

export function getSchemeBundle(schemeId: string) {
  return api.get<SchemeBundle>(`${schBase(schemeId)}/bundle`)
}

export function validateScheme(schemeId: string) {
  return api.post<ValidationReport>(`${schBase(schemeId)}/validate`)
}

export function validateSchemePayload(schemeId: string, data: SystemSchemeUpdate) {
  return api.post<ValidationReport>(`${schBase(schemeId)}/validate-payload`, data)
}

export function validateStrategy(schemeId: string) {
  return api.post<ValidationReport>(`${schBase(schemeId)}/validate-strategy`)
}

export function validateStrategyPayload(schemeId: string, data: SystemSchemeUpdate) {
  return api.post<ValidationReport>(`${schBase(schemeId)}/validate-strategy-payload`, data)
}

// ---- equipment search ----

export function searchEquipment(params: EquipmentSearchParams) {
  return api.get<EquipmentBrief[]>('/equipment-search', { params })
}
