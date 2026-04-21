<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, Check } from '@element-plus/icons-vue'
import {
  adminListUsers,
  adminUpdateUser,
  adminApproveUser,
  adminDeleteUser,
  adminListActivityLogs,
} from '@/api/users'
import type { User, UserActivityLog } from '@/types/user'

const { t } = useI18n()

const tab = ref<'users' | 'logs'>('users')
const statusFilter = ref<'all' | 'pending' | 'active' | 'disabled'>('all')
const roleFilter = ref<'all' | 'admin' | 'user'>('all')
const keyword = ref('')
const users = ref<User[]>([])
const logs = ref<UserActivityLog[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    if (tab.value === 'users') {
      const { data } = await adminListUsers({
        status: statusFilter.value,
        role: roleFilter.value,
        keyword: keyword.value || undefined,
      })
      users.value = data
    } else {
      const { data } = await adminListActivityLogs({ limit: 200 })
      logs.value = data
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function approve(u: User) {
  await adminApproveUser(u.id)
  ElMessage.success(t('admin.approveSuccess'))
  await load()
}

async function setRole(u: User, role: 'admin' | 'user') {
  await adminUpdateUser(u.id, { role })
  ElMessage.success(t('common.updateSuccess'))
  await load()
}

async function setStatus(u: User, status: 'active' | 'disabled') {
  await adminUpdateUser(u.id, { status })
  ElMessage.success(t('common.updateSuccess'))
  await load()
}

async function del(u: User) {
  await ElMessageBox.confirm(t('admin.deleteUserConfirm', { name: u.username }), t('common.warning'), { type: 'warning' })
  await adminDeleteUser(u.id)
  ElMessage.success(t('common.deleteSuccess'))
  await load()
}
</script>

<template>
  <div class="admin-view">
    <div class="page-header">
      <h1>{{ t('admin.title') }}</h1>
    </div>

    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane :label="t('admin.users')" name="users" />
      <el-tab-pane :label="t('admin.activityLogs')" name="logs" />
    </el-tabs>

    <!-- Users Tab -->
    <div v-if="tab === 'users'">
      <div class="filter-bar">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          :placeholder="t('admin.searchPlaceholder')"
          clearable
          style="width: 240px"
          @change="load"
        />
        <el-select v-model="statusFilter" style="width: 140px" @change="load">
          <el-option :label="t('admin.statusAll')" value="all" />
          <el-option :label="t('admin.statusPending')" value="pending" />
          <el-option :label="t('admin.statusActive')" value="active" />
          <el-option :label="t('admin.statusDisabled')" value="disabled" />
        </el-select>
        <el-select v-model="roleFilter" style="width: 140px" @change="load">
          <el-option :label="t('admin.roleAll')" value="all" />
          <el-option :label="t('account.admin')" value="admin" />
          <el-option :label="t('account.user')" value="user" />
        </el-select>
      </div>

      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" :label="t('account.username')" width="160" />
        <el-table-column prop="full_name" :label="t('account.fullName')" width="120" />
        <el-table-column prop="email" :label="t('account.email')" min-width="180" show-overflow-tooltip />
        <el-table-column :label="t('account.role')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? t('account.admin') : t('account.user') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('admin.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : row.status === 'pending' ? 'warning' : 'info'" size="small">
              {{ t(`admin.status${row.status.charAt(0).toUpperCase() + row.status.slice(1)}`) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('account.lastLogin')" width="160">
          <template #default="{ row }">
            {{ row.last_login_at ? new Date(row.last_login_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column :label="t('common.operation')" width="320" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="success" size="small" :icon="Check" @click="approve(row)">
              {{ t('admin.approve') }}
            </el-button>
            <el-button v-if="row.status === 'active' && row.role === 'user'" size="small" @click="setRole(row, 'admin')">
              {{ t('admin.makeAdmin') }}
            </el-button>
            <el-button v-if="row.role === 'admin'" size="small" @click="setRole(row, 'user')">
              {{ t('admin.demote') }}
            </el-button>
            <el-button v-if="row.status === 'active'" type="warning" size="small" @click="setStatus(row, 'disabled')">
              {{ t('admin.disable') }}
            </el-button>
            <el-button v-if="row.status === 'disabled'" size="small" @click="setStatus(row, 'active')">
              {{ t('admin.enable') }}
            </el-button>
            <el-button type="danger" size="small" :icon="Delete" text @click="del(row)" />
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Activity Logs Tab -->
    <div v-else>
      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="action" :label="t('account.action')" width="140" />
        <el-table-column prop="target" :label="t('account.target')" min-width="180" />
        <el-table-column prop="ip_address" :label="'IP'" width="160" />
        <el-table-column prop="user_id" :label="'User ID'" width="280" show-overflow-tooltip />
        <el-table-column :label="t('account.time')" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.admin-view { padding: 24px 28px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.page-header h1 { margin: 0 0 8px 0; font-size: 22px; color: #0f172a; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
</style>
