<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Moon, Sunny, Connection, Lock, SwitchButton } from '@element-plus/icons-vue'
import { getMe, updateMe, getMyActivityLogs } from '@/api/users'
import type { User, UserActivityLog } from '@/types/user'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { setLocale, getLocale } from '@/i18n'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { currentTheme, toggleTheme } = useTheme()

const currentLang = ref(getLocale() === 'en-US' ? 'en-US' : 'zh-CN')
function switchLang(lang: 'zh-CN' | 'en-US') {
  currentLang.value = lang
  setLocale(lang)
}

const isAdmin = computed(() => authStore.isAdmin)

async function handleLogout() {
  await ElMessageBox.confirm(t('account.logoutConfirm') as string || '确定要退出登录吗？', t('common.tip') as string || '提示', { type: 'warning' })
  authStore.logout()
  router.push('/login')
}

const user = ref<User | null>(null)
const logs = ref<UserActivityLog[]>([])
const loading = ref(false)

const form = ref({
  email: '',
  full_name: '',
  password: '',
  password2: '',
})

async function load() {
  loading.value = true
  try {
    const { data } = await getMe()
    user.value = data
    form.value.email = data.email || ''
    form.value.full_name = data.full_name || ''
    const logsRes = await getMyActivityLogs()
    logs.value = logsRes.data
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function save() {
  if (form.value.password && form.value.password !== form.value.password2) {
    ElMessage.warning(t('account.passwordMismatch'))
    return
  }
  const data: Record<string, string> = {}
  if (form.value.email !== (user.value?.email || '')) data.email = form.value.email
  if (form.value.full_name !== (user.value?.full_name || '')) data.full_name = form.value.full_name
  if (form.value.password) data.password = form.value.password
  if (Object.keys(data).length === 0) {
    ElMessage.info(t('account.nothingChanged'))
    return
  }
  const { data: updated } = await updateMe(data)
  user.value = updated
  form.value.password = ''
  form.value.password2 = ''
  ElMessage.success(t('account.saveSuccess'))
}
</script>

<template>
  <div class="account-view" v-loading="loading">
    <div class="page-header">
      <h1>{{ t('account.title') }}</h1>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :md="12">
        <el-card class="account-card">
          <template #header>{{ t('account.basicInfo') }}</template>
          <el-form label-width="100px">
            <el-form-item :label="t('account.username')">
              <el-input :model-value="user?.username" disabled />
            </el-form-item>
            <el-form-item :label="t('account.role')">
              <el-tag :type="user?.role === 'admin' ? 'danger' : 'info'">
                {{ user?.role === 'admin' ? t('account.admin') : t('account.user') }}
              </el-tag>
            </el-form-item>
            <el-form-item :label="t('account.fullName')">
              <el-input v-model="form.full_name" />
            </el-form-item>
            <el-form-item :label="t('account.email')">
              <el-input v-model="form.email" />
            </el-form-item>
            <el-form-item :label="t('account.lastLogin')">
              <span>{{ user?.last_login_at ? new Date(user.last_login_at).toLocaleString() : '-' }}</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card class="account-card">
          <template #header>{{ t('account.changePassword') }}</template>
          <el-form label-width="120px">
            <el-form-item :label="t('account.newPassword')">
              <el-input v-model="form.password" type="password" show-password />
            </el-form-item>
            <el-form-item :label="t('account.confirmPassword')">
              <el-input v-model="form.password2" type="password" show-password />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <div class="actions">
      <el-button type="primary" @click="save">{{ t('common.save') }}</el-button>
    </div>

    <!-- 偏好设置（主题 / 语言） -->
    <el-card class="account-card" style="margin-top: 16px">
      <template #header>{{ t('account.preferences') || '偏好设置' }}</template>
      <div class="pref-row">
        <div class="pref-label">
          <el-icon :size="16"><component :is="currentTheme === 'dark' ? Sunny : Moon" /></el-icon>
          <span>{{ t('account.theme') || '主题模式' }}</span>
        </div>
        <el-switch
          :model-value="currentTheme === 'dark'"
          @update:model-value="toggleTheme"
          :active-text="t('account.themeDark') || '深色'"
          :inactive-text="t('account.themeLight') || '浅色'"
          inline-prompt
        />
      </div>
      <div class="pref-row">
        <div class="pref-label">
          <el-icon :size="16"><Connection /></el-icon>
          <span>{{ t('account.language') || '语言' }}</span>
        </div>
        <el-radio-group :model-value="currentLang" @update:model-value="(val) => switchLang(val as 'zh-CN' | 'en-US')" size="small">
          <el-radio-button label="zh-CN">中文</el-radio-button>
          <el-radio-button label="en-US">English</el-radio-button>
        </el-radio-group>
      </div>
    </el-card>

    <!-- 快捷入口（系统管理 / 退出） -->
    <el-card class="account-card" style="margin-top: 16px">
      <template #header>{{ t('account.shortcuts') || '快捷入口' }}</template>
      <div class="shortcut-list">
        <button v-if="isAdmin" class="shortcut-item" @click="router.push('/admin/users')">
          <el-icon :size="18"><Lock /></el-icon>
          <span>{{ t('dashboard.nav.admin') }}</span>
        </button>
        <button class="shortcut-item shortcut-item--danger" @click="handleLogout">
          <el-icon :size="18"><SwitchButton /></el-icon>
          <span>{{ t('common.logout') }}</span>
        </button>
      </div>
    </el-card>

    <el-card class="account-card" style="margin-top: 16px">
      <template #header>{{ t('account.activityLogs') }}</template>
      <el-table :data="logs" stripe max-height="360">
        <el-table-column prop="action" :label="t('account.action')" width="120" />
        <el-table-column prop="target" :label="t('account.target')" />
        <el-table-column prop="ip_address" :label="'IP'" width="140" />
        <el-table-column :label="t('account.time')" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.account-view { padding: 24px 28px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.page-header h1 { margin: 0 0 16px 0; font-size: 22px; color: var(--text-primary); }
.account-card { margin-bottom: 16px; }
.actions { display: flex; justify-content: flex-end; margin-top: 8px; }
.pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.pref-row:last-child { border-bottom: none; }
.pref-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-body);
  font-size: var(--font-size-sm);
}
.shortcut-list { display: flex; flex-direction: column; gap: 8px; }
.shortcut-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--surface-sunken);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-size-sm);
  color: var(--text-body);
  transition: all var(--motion-fast) var(--easing-standard);
  text-align: left;
}
.shortcut-item:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary);
  background: var(--brand-primary-soft);
}
.shortcut-item--danger:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
  background: var(--color-danger-soft);
}
@media (max-width: 768px) {
  .account-view { padding: 16px 12px; }
}
</style>
