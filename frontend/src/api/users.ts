import api from '@/api'
import type {
  User,
  UserActivityLog,
  UserUpdate,
  AdminUserUpdate,
  RegisterRequest,
} from '@/types/user'

export function getMe() {
  return api.get<User>('/auth/me')
}

export function updateMe(data: UserUpdate) {
  return api.patch<User>('/auth/me', data)
}

export function register(data: RegisterRequest) {
  return api.post<User>('/auth/register', data)
}

export function getMyActivityLogs(limit = 100) {
  return api.get<UserActivityLog[]>('/me/activity-logs', { params: { limit } })
}

// Admin
export function adminListUsers(params: {
  status?: 'all' | 'pending' | 'active' | 'disabled'
  role?: 'all' | 'admin' | 'user'
  keyword?: string
}) {
  return api.get<User[]>('/admin/users', { params })
}

export function adminUpdateUser(id: string, data: AdminUserUpdate) {
  return api.patch<User>(`/admin/users/${id}`, data)
}

export function adminApproveUser(id: string) {
  return api.post<User>(`/admin/users/${id}/approve`)
}

export function adminDeleteUser(id: string) {
  return api.delete(`/admin/users/${id}`)
}

export function adminListActivityLogs(params: { user_id?: string; limit?: number } = {}) {
  return api.get<UserActivityLog[]>('/admin/activity-logs', { params })
}
