<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { register } from '@/api/users'

const router = useRouter()

const form = ref({ username: '', password: '', password2: '', email: '', full_name: '' })
const loading = ref(false)

async function handleRegister() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (form.value.password !== form.value.password2) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await register({
      username: form.value.username,
      password: form.value.password,
      email: form.value.email || undefined,
      full_name: form.value.full_name || undefined,
    })
    ElMessage.success('注册成功，待管理员审批后方可登录')
    router.push('/login')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <h1>HVAC仿真平台</h1>
        <p>注册新账号</p>
      </div>
      <el-form :model="form" @submit.prevent="handleRegister" class="login-form">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.full_name" placeholder="姓名（可选）" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.email" placeholder="邮箱（可选）" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password2" type="password" placeholder="确认密码" prefix-icon="Lock" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="handleRegister">
            注册
          </el-button>
        </el-form-item>
        <div class="register-hint">
          已有账号？<el-link type="primary" @click="router.push('/login')">立即登录</el-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0f172a;
}
.login-card {
  width: 420px;
  padding: 36px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  backdrop-filter: blur(16px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}
.login-header { text-align: center; margin-bottom: 28px; }
.login-header h1 { margin: 0 0 8px; font-size: 24px; color: #e2e8f0; }
.login-header p { margin: 0; color: #64748b; font-size: 13px; }
.register-hint { text-align: center; color: #94a3b8; font-size: 13px; margin-top: -8px; }
.login-card :deep(.el-input__wrapper) {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: none !important;
  border-radius: 10px;
}
.login-card :deep(.el-input__inner) { color: #e2e8f0; }
.login-card :deep(.el-button--primary) {
  background: linear-gradient(135deg, #06b6d4, #0284c7);
  border: none;
  border-radius: 10px;
  font-weight: 600;
}
</style>
