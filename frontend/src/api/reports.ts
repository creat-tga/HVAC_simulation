import api from '@/api'
import type { EnergyReport, CostReport, CarbonReport } from '@/types/report'

export function getEnergyReport(resultId: string) {
  return api.get<EnergyReport>(`/reports/energy/${resultId}`)
}

export function getCostReport(resultId: string) {
  return api.get<CostReport>(`/reports/cost/${resultId}`)
}

export function getCarbonReport(resultId: string) {
  return api.get<CarbonReport>(`/reports/carbon/${resultId}`)
}
