<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { getMe, updateMe, getMyActivityLogs } from '@/api/users'
import type { User, UserActivityLog } from '@/types/user'

const { t } = useI18n()

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
.page-header h1 { margin: 0 0 16px 0; font-size: 22px; color: #0f172a; }
.account-card { margin-bottom: 16px; }
.actions { display: flex; justify-content: flex-end; margin-top: 8px; }
</style>
