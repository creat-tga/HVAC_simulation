import { ref } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'hvac_theme'

const currentTheme = ref<Theme>('light')
let initialized = false

function applyTheme(theme: Theme) {
  currentTheme.value = theme
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* localStorage may be unavailable */
  }
}

function resolveInitialTheme(): Theme {
  let saved: string | null = null
  try {
    saved = localStorage.getItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
  if (saved === 'dark' || saved === 'light') return saved
  const systemPrefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  return systemPrefersDark ? 'dark' : 'light'
}

export function initTheme() {
  if (initialized) return
  initialized = true
  applyTheme(resolveInitialTheme())
}

export function useTheme() {
  function toggleTheme() {
    applyTheme(currentTheme.value === 'dark' ? 'light' : 'dark')
  }
  function setTheme(theme: Theme) {
    applyTheme(theme)
  }
  return { currentTheme, toggleTheme, setTheme }
}
