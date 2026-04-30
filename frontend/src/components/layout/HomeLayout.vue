<script setup lang="ts">
/**
 * Top-level home layout: left sidebar with module nav, right content via router-view.
 * Used as parent route for /, /projects, /library/*, /account, /admin/users.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import {
  HomeFilled,
  FolderOpened,
  OfficeBuilding,
  Sunny,
  Setting,
  User,
  Lock,
} from '@element-plus/icons-vue'
import TopActionBar from '@/components/layout/TopActionBar.vue'
import MobileBottomNav from '@/components/layout/MobileBottomNav.vue'
import { useResponsive } from '@/composables/useResponsive'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const { isMobile } = useResponsive()

const SIDEBAR_NAV_COLOR = 'var(--brand-primary)'

interface NavItem {
  key: string
  label: string
  icon: any
  path: string
  matches: string[]
  color: string
}

const navItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { key: 'home', label: t('dashboard.nav.home'), icon: HomeFilled, path: '/', matches: ['home'], color: SIDEBAR_NAV_COLOR },
    { key: 'projects', label: t('dashboard.nav.projects'), icon: FolderOpened, path: '/projects', matches: ['projectsList'], color: SIDEBAR_NAV_COLOR },
    { key: 'buildings', label: t('dashboard.nav.buildings'), icon: OfficeBuilding, path: '/library/buildings', matches: ['libBuildings'], color: SIDEBAR_NAV_COLOR },
    { key: 'weather', label: t('dashboard.nav.weather'), icon: Sunny, path: '/library/weather', matches: ['libWeather'], color: SIDEBAR_NAV_COLOR },
    { key: 'equipment', label: t('dashboard.nav.equipment'), icon: Setting, path: '/library/equipment', matches: ['libEquipment'], color: SIDEBAR_NAV_COLOR },
    { key: 'account', label: t('dashboard.nav.account'), icon: User, path: '/account', matches: ['account'], color: SIDEBAR_NAV_COLOR },
  ]
  if (authStore.isAdmin) {
    items.push({ key: 'admin', label: t('dashboard.nav.admin'), icon: Lock, path: '/admin/users', matches: ['adminUsers'], color: SIDEBAR_NAV_COLOR })
  }
  return items
})

const isActive = (item: NavItem) => item.matches.includes(route.name as string)
</script>

<template>
  <div class="home-layout" :class="{ 'is-mobile': isMobile }">
    <aside v-if="!isMobile" class="hl-sidebar">
      <div class="hl-brand">
        <div class="hl-brand-logo">
          <el-icon :size="20"><HomeFilled /></el-icon>
        </div>
        <div class="hl-brand-text">
          <div class="hl-brand-title">HVAC</div>
          <div class="hl-brand-sub">Simulation</div>
        </div>
      </div>

      <nav class="hl-nav">
        <div
          v-for="item in navItems"
          :key="item.key"
          class="hl-nav-item"
          :class="{ active: isActive(item) }"
          :style="{ '--c': item.color } as any"
          @click="router.push(item.path)"
        >
          <el-icon :size="18" class="hl-nav-icon"><component :is="item.icon" /></el-icon>
          <span class="hl-nav-label">{{ item.label }}</span>
        </div>
      </nav>

      <div class="hl-footer">
        <div class="hl-user">
          <div class="hl-avatar">{{ authStore.username.charAt(0).toUpperCase() }}</div>
          <div class="hl-user-info">
            <div class="hl-user-name">{{ authStore.username }}</div>
            <div class="hl-user-role">{{ authStore.isAdmin ? t('account.admin') : t('account.user') }}</div>
          </div>
        </div>
      </div>
    </aside>

    <main class="hl-main">
      <TopActionBar />
      <div class="hl-content">
        <router-view />
      </div>
    </main>
    <MobileBottomNav v-if="isMobile" />
  </div>
</template>

<style scoped>
.home-layout {
  display: flex;
  height: 100vh;
  height: 100dvh;
  background: linear-gradient(135deg, #f8fafc 0%, #eef2f7 100%);
}

.hl-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.85) 100%);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(226, 232, 240, 0.6);
  display: flex;
  flex-direction: column;
  padding: 18px 12px;
  gap: 6px;
}

.hl-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px 16px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
  margin-bottom: 8px;
}
.hl-brand-logo {
  width: 36px; height: 36px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  background: var(--brand-primary-gradient);
  color: white;
  flex-shrink: 0;
}
.hl-brand-title { font-size: 16px; font-weight: 700; color: #0f172a; line-height: 1.1; }
.hl-brand-sub { font-size: 11px; color: #94a3b8; letter-spacing: 0.05em; text-transform: uppercase; }

.hl-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow-y: auto;
}

.hl-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 500;
  color: #475569;
  transition: all 0.18s ease;
  user-select: none;
  position: relative;
}

.hl-nav-item:hover {
  background: rgba(15, 23, 42, 0.04);
  color: var(--c);
}
.hl-nav-item:hover .hl-nav-icon { color: var(--c); }

.hl-nav-item.active {
  background: color-mix(in srgb, var(--c) 12%, transparent);
  color: var(--c);
  font-weight: 600;
}
.hl-nav-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 8px; bottom: 8px;
  width: 3px; border-radius: 2px;
  background: var(--c);
}
.hl-nav-item.active .hl-nav-icon { color: var(--c); }
.hl-nav-icon { color: #94a3b8; transition: color 0.18s; }

.hl-footer {
  border-top: 1px solid rgba(226, 232, 240, 0.5);
  padding-top: 12px;
}
.hl-user {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(241, 245, 249, 0.6);
}
.hl-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--brand-primary-gradient);
  color: white; font-weight: 600; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.hl-user-name { font-size: 13px; font-weight: 600; color: #0f172a; line-height: 1.2; }
.hl-user-role { font-size: 11px; color: #94a3b8; }

.hl-main {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.hl-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

@media (max-width: 768px) {
  .home-layout { flex-direction: column; }
  .hl-main { padding-bottom: 56px; }
}
</style>
