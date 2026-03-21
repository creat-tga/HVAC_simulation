<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { setLocale, getLocale } from '@/i18n'
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()

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
    <div class="header-left" @click="router.push('/')" style="cursor: pointer">
      <img src="@/assets/logo.svg" alt="Logo" class="platform-logo" />
      <h1 class="platform-title">中央空调系统仿真平台</h1>
      <span class="platform-title-en">HVAC Simulation Platform</span>
    </div>
    <div class="header-right">
      <el-dropdown @command="switchLanguage" trigger="click">
        <el-button text>
          🌐 {{ currentLang === 'zh-CN' ? '中文' : 'English' }}
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
          👤 {{ authStore.username }}
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
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.platform-logo {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.platform-title {
  margin: 0;
  font-size: 18px;
  color: var(--el-color-primary);
  font-weight: 600;
  user-select: none;
  white-space: nowrap;
}

.platform-title-en {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  user-select: none;
  white-space: nowrap;
  margin-left: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  cursor: pointer;
  color: var(--el-text-color-regular);
  font-size: 14px;
}
</style>
