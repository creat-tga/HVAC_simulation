<script setup lang="ts">
/**
 * Compact top action bar for full-screen layouts (HomeLayout / ProjectWorkspaceLayout).
 * Provides language switcher and user dropdown without the heavy AppHeader.
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocale, getLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { Connection, User, ArrowDown, Moon, Sunny } from '@element-plus/icons-vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const currentLang = ref(getLocale() === 'en-US' ? 'en-US' : 'zh-CN')
const currentTheme = ref<'light' | 'dark'>('light')

function applyTheme(theme: 'light' | 'dark') {
  currentTheme.value = theme
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('hvac_theme', theme)
}

function toggleTheme() {
  applyTheme(currentTheme.value === 'dark' ? 'light' : 'dark')
}

onMounted(() => {
  const saved = localStorage.getItem('hvac_theme')
  const systemPrefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  applyTheme(saved === 'dark' || (!saved && systemPrefersDark) ? 'dark' : 'light')
})

function switchLanguage(lang: string) {
  currentLang.value = lang
  setLocale(lang)
  window.location.reload()
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

function gotoAccount() {
  router.push('/account')
}
</script>

<template>
  <div class="top-bar">
    <slot name="left" />
    <div class="spacer" />
    <button class="tb-btn tb-btn--theme" @click="toggleTheme">
      <el-icon :size="14"><component :is="currentTheme === 'dark' ? Sunny : Moon" /></el-icon>
      <span>{{ currentTheme === 'dark' ? '浅色' : '深色' }}</span>
    </button>
    <el-dropdown @command="switchLanguage" trigger="click">
      <button class="tb-btn">
        <el-icon :size="14"><Connection /></el-icon>
        <span>{{ currentLang === 'en-US' ? 'EN' : '中文' }}</span>
        <el-icon :size="12"><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="zh-CN">中文</el-dropdown-item>
          <el-dropdown-item command="en-US">English</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <el-dropdown trigger="click">
      <button class="tb-btn">
        <el-icon :size="14"><User /></el-icon>
        <span>{{ authStore.username }}</span>
        <el-icon :size="12"><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item @click="gotoAccount">{{ t('dashboard.nav.account') }}</el-dropdown-item>
          <el-dropdown-item divided @click="handleLogout">{{ t('common.logout') }}</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.top-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
  flex-shrink: 0;
  height: 48px;
  box-sizing: border-box;
}
.spacer { flex: 1; }
.tb-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 12.5px;
  color: #475569;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s;
}
.tb-btn:hover {
  background: rgba(15, 23, 42, 0.04);
  color: #0f172a;
}
.tb-btn:focus-visible {
  outline: none;
  border-color: rgba(8, 145, 178, 0.4);
}
</style>
