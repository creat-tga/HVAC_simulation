<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import SliderVerify from '@/components/login/SliderVerify.vue'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const sliderVerified = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (!sliderVerified.value) {
    ElMessage.warning('请先完成滑块验证')
    return
  }
  loading.value = true
  try {
    const { data } = await login(form.value)
    authStore.setAuth(data.access_token, data.username)
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    // Error handled by axios interceptor
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
        <p>建筑负荷模拟与系统能耗分析</p>
      </div>
      <el-form :model="form" @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <SliderVerify @success="sliderVerified = true" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            style="width: 100%"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
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
  position: relative;
  overflow: hidden;
}

/* Gradient blob background */
.login-page::before {
  content: '';
  position: absolute;
  top: -15%;
  left: -15%;
  width: 55%;
  height: 55%;
  border-radius: 50%;
  background: rgba(6, 182, 212, 0.15);
  filter: blur(80px);
  animation: login-blob 18s infinite alternate ease-in-out;
}

.login-page::after {
  content: '';
  position: absolute;
  bottom: -15%;
  right: -15%;
  width: 60%;
  height: 60%;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.12);
  filter: blur(80px);
  animation: login-blob 18s infinite alternate-reverse ease-in-out;
}

@keyframes login-blob {
  0% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(30px, -30px) scale(1.05); }
  100% { transform: translate(0, 0) scale(1); }
}

.login-card {
  width: 420px;
  padding: 40px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  position: relative;
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  margin: 0 0 8px;
  font-size: 26px;
  color: #e2e8f0;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.login-header p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
}

.login-form {
  margin-top: 20px;
}

/* Override Element Plus input styles for dark login */
.login-card :deep(.el-input__wrapper) {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: none !important;
  border-radius: 10px;
}

.login-card :deep(.el-input__inner) {
  color: #e2e8f0;
}

.login-card :deep(.el-input__inner::placeholder) {
  color: #64748b;
}

.login-card :deep(.el-input__prefix .el-icon) {
  color: #64748b;
}

.login-card :deep(.el-button--primary) {
  background: linear-gradient(135deg, #06b6d4, #0284c7);
  border: none;
  border-radius: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.login-card :deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #22d3ee, #0891b2);
}

@media (max-width: 768px) {
  .login-card {
    width: 92%;
    max-width: 420px;
    padding: 28px 20px;
  }

  .login-header h1 {
    font-size: 22px;
  }
}
</style>
