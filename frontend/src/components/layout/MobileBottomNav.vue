<script setup lang="ts">
/**
 * MobileBottomNav: 移动端全局底部 tab bar (主页/工程/模板/我的)
 * 在 HomeLayout 中按 isMobile 挂载，workspace 内由各自布局负责。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { HomeFilled, FolderOpened, Files, User } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

interface Tab {
  key: string
  label: string
  icon: any
  path: string
  matches: string[]
}

const tabs = computed<Tab[]>(() => [
  { key: 'home', label: t('dashboard.nav.home'), icon: HomeFilled, path: '/', matches: ['home'] },
  { key: 'projects', label: t('dashboard.nav.projects'), icon: FolderOpened, path: '/projects', matches: ['projectsList'] },
  { key: 'library', label: t('mobileNav.templates'), icon: Files, path: '/library', matches: ['libraryHub', 'libBuildings', 'libWeather', 'libEquipment'] },
  { key: 'mine', label: t('mobileNav.mine'), icon: User, path: '/account', matches: ['account', 'adminUsers'] },
])

function isActive(tab: Tab) {
  return tab.matches.includes(route.name as string)
}

function go(tab: Tab) {
  if (route.path !== tab.path) router.push(tab.path)
}
</script>

<template>
  <nav class="mb-nav" role="navigation" aria-label="主导航">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      class="mb-tab"
      :class="{ active: isActive(tab) }"
      @click="go(tab)"
    >
      <el-icon :size="20"><component :is="tab.icon" /></el-icon>
      <span class="mb-tab-label">{{ tab.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.mb-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  padding: 4px 4px calc(4px + env(safe-area-inset-bottom, 0px));
  background: var(--surface-base);
  border-top: 1px solid var(--border-subtle);
  box-shadow: 0 -2px 8px rgba(15, 23, 42, 0.06);
  z-index: 1000;
}
.mb-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 6px 4px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--motion-fast) var(--easing-standard);
  -webkit-tap-highlight-color: transparent;
}
.mb-tab:active { background: var(--color-neutral-100); }
.mb-tab.active {
  color: var(--brand-primary);
}
.mb-tab-label {
  font-size: 10px;
  line-height: 1.2;
}
</style>
