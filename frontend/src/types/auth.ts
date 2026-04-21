export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  username: string
  role: string
}

export interface UserInfo {
  username: string
  token: string
  role: string
}
