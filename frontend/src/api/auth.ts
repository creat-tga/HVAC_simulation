import api from '@/api'
import type { LoginRequest, TokenResponse } from '@/types/auth'

export function login(data: LoginRequest) {
  return api.post<TokenResponse>('/auth/login', data)
}
