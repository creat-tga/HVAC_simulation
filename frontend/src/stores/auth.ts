import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const TOKEN_KEY = 'hvac_token'
const USER_KEY = 'hvac_user'
const ROLE_KEY = 'hvac_role'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const username = ref<string>(localStorage.getItem(USER_KEY) || '')
  const role = ref<string>(localStorage.getItem(ROLE_KEY) || 'user')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  function setAuth(newToken: string, newUsername: string, newRole = 'user') {
    token.value = newToken
    username.value = newUsername
    role.value = newRole
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, newUsername)
    localStorage.setItem(ROLE_KEY, newRole)
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = 'user'
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(ROLE_KEY)
  }

  return { token, username, role, isLoggedIn, isAdmin, setAuth, logout }
})
