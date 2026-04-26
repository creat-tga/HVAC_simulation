<script setup lang="ts">
/**
 * Compact top action bar for full-screen layouts (HomeLayout / ProjectWorkspaceLayout).
 * Provides language switcher and user dropdown without the heavy AppHeader.
 */
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocale, getLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { useResponsive } from '@/composables/useResponsive'
import { Connection, User, ArrowDown, ArrowLeft, Moon, Sunny } from '@element-plus/icons-vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { isMobile } = useResponsive()

const currentLang = ref(getLocale() === 'en-US' ? 'en-US' : 'zh-CN')
const { currentTheme, toggleTheme } = useTheme()

const mobileBackPath = computed<string | null>(() => {
  const v = route.meta?.mobileBack
  if (typeof v === 'string') return v
  if (typeof v === 'function') {
    try { return (v as (r: typeof route) => string)(route) || null } catch { return null }
  }
  return null
})
function goMobileBack() {
  if (mobileBackPath.value) router.push(mobileBackPath.value)
}

const mobileTitle = computed(() => {
  // 仅在有 mobileBack 的非一级页面显示中央标题
  if (!isMobile.value || !mobileBackPath.value) return ''
  if (route.meta?.mobileNoTitle === true) return ''
  return (route.meta?.title as string | undefined) || ''
})

// 页面自带顶栏时（如方案详情页），移动端隐藏全局 TopActionBar。
const hideOnMobile = computed(() => isMobile.value && route.meta?.mobileCustomTopbar === true)

function switchLanguage(lang: string) {
  currentLang.value = lang
  setLocale(lang)
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
  <div
    v-if="!hideOnMobile"
    class="top-bar"
    :class="{ 'top-bar--mobile': isMobile }"
  >
    <button
      v-if="isMobile && mobileBackPath"
      class="tb-back"
      :aria-label="t('workspace.backToProjects') || '返回'"
      @click="goMobileBack"
    >
      <el-icon :size="20"><ArrowLeft /></el-icon>
    </button>
    <slot name="left" />
    <h1 v-if="mobileTitle" class="tb-title">{{ mobileTitle }}</h1>
    <div class="spacer" />
    <template v-if="!isMobile">
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
    </template>
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
.top-bar--mobile {
  padding: 6px 8px;
  background: transparent;
  border-bottom: none;
  min-height: 44px;
}
.top-bar--mobile:has(> .spacer:only-child) {
  display: none;
}
.tb-title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.01em;
  pointer-events: none;
  max-width: 60vw;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.top-bar--mobile { position: relative; }
.tb-back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: transparent;
  border: none;
  color: var(--text-body);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background var(--motion-fast) var(--easing-standard);
}
.tb-back:active { background: var(--color-neutral-100); }
</style>
