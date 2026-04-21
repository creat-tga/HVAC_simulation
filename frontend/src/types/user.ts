// User & account types

export interface User {
  id: string
  username: string
  email: string | null
  full_name: string | null
  role: 'admin' | 'user'
  status: 'pending' | 'active' | 'disabled'
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export interface UserActivityLog {
  id: string
  user_id: string
  action: string
  target: string | null
  detail: string | null
  ip_address: string | null
  created_at: string
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string
  full_name?: string
}

export interface UserUpdate {
  email?: string
  full_name?: string
  password?: string
}

export interface AdminUserUpdate {
  role?: 'admin' | 'user'
  status?: 'pending' | 'active' | 'disabled'
  is_active?: boolean
}
