<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { setLocale, getLocale } from '@/i18n'
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Fold, Connection, User, Moon, Sunny } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import { useTheme } from '@/composables/useTheme'

const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const { isMobile, toggleSidebar } = useResponsive()
const { currentTheme, toggleTheme } = useTheme()

const currentLang = ref(getLocale() === 'en-US' ? 'en-US' : 'zh-CN')

function switchLanguage(lang: string) {
  currentLang.value = lang
  setLocale(lang)
}

async function handleLogout() {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-header class="app-header">
    <div class="header-left">
      <el-button
        v-if="isMobile"
        text
        class="menu-btn"
        @click="toggleSidebar"
      >
        <el-icon :size="20"><Fold /></el-icon>
      </el-button>
      <div class="logo-group" @click="router.push('/')" style="cursor: pointer">
        <img src="@/assets/logo.svg" alt="Logo" class="platform-logo" />
        <h1 class="platform-title">中央空调系统仿真平台</h1>
        <span v-if="!isMobile" class="platform-title-en">HVAC Simulation Platform</span>
      </div>
    </div>
    <div class="header-right">
      <el-tooltip :content="currentTheme === 'dark' ? '切换到浅色' : '切换到深色'" placement="bottom" :show-after="300">
        <el-button text class="theme-btn" @click="toggleTheme">
          <el-icon :size="16"><component :is="currentTheme === 'dark' ? Sunny : Moon" /></el-icon>
        </el-button>
      </el-tooltip>
      <el-dropdown @command="switchLanguage" trigger="click">
        <el-button text class="lang-btn">
          <el-icon :size="16"><Connection /></el-icon>
          <span v-if="!isMobile">{{ currentLang === 'zh-CN' ? '中文' : 'English' }}</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="zh-CN" :class="{ active: currentLang === 'zh-CN' }">
              中文
            </el-dropdown-item>
            <el-dropdown-item command="en-US" :class="{ active: currentLang === 'en-US' }">
              English
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-dropdown trigger="click">
        <span class="user-info">
          <el-icon :size="16"><User /></el-icon>
          <span v-if="!isMobile">{{ authStore.username }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="handleLogout">
              {{ t('common.logout') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </el-header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: var(--shadow-xs);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.menu-btn {
  padding: 4px;
}

.platform-logo {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  padding: 4px;
  background: rgba(6, 182, 212, 0.1);
  border-radius: var(--radius-md);
}

.platform-title {
  margin: 0;
  font-size: 17px;
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
  user-select: none;
  white-space: nowrap;
  letter-spacing: -0.01em;
}

.platform-title-en {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  user-select: none;
  white-space: nowrap;
  margin-left: 2px;
  letter-spacing: 0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  cursor: pointer;
  color: var(--color-neutral-600);
  font-size: var(--font-size-base);
  padding: 6px 12px;
  border-radius: var(--radius-md);
  transition: background 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.user-info:hover {
  background: rgba(241, 245, 249, 0.8);
}

@media (max-width: 768px) {
  .app-header {
    padding: 0 8px;
    height: 48px;
  }

  .header-left {
    gap: 4px;
    overflow: hidden;
    flex: 1;
    min-width: 0;
  }

  .logo-group {
    gap: 6px;
    overflow: hidden;
    min-width: 0;
  }

  .platform-logo {
    width: 26px;
    height: 26px;
  }

  .platform-title {
    font-size: var(--font-size-base);
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .header-right {
    gap: 2px;
    flex-shrink: 0;
  }

  .user-info {
    padding: 4px 6px;
    font-size: var(--font-size-sm);
  }
}
</style>
