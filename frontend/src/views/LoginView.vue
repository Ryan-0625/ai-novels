<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeTab = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const email = ref('')
const tenantId = ref('default')
const loading = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await authStore.login(username.value, password.value, tenantId.value)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/tasks/create'
    router.push(redirect)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!username.value || !password.value) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (password.value.length < 6) {
    ElMessage.warning('密码至少6位')
    return
  }
  loading.value = true
  try {
    await authStore.register(username.value, password.value, email.value, tenantId.value)
    ElMessage.success('注册成功')
    router.push('/tasks/create')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-view">
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <el-icon :size="28"><MagicStick /></el-icon>
        </div>
        <h1 class="login-title">AI 小说生成系统</h1>
        <p class="login-subtitle">登录以管理您的小说创作</p>
      </div>

      <el-tabs v-model="activeTab" class="login-tabs" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form @submit.prevent="handleLogin" class="login-form">
            <el-input
              v-model="username"
              placeholder="用户名"
              :prefix-icon="User"
              size="large"
              class="login-input"
            />
            <el-input
              v-model="password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              size="large"
              class="login-input"
              show-password
            />
            <el-input
              v-model="tenantId"
              placeholder="租户ID (默认: default)"
              size="large"
              class="login-input"
            />
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form @submit.prevent="handleRegister" class="login-form">
            <el-input
              v-model="username"
              placeholder="用户名"
              :prefix-icon="User"
              size="large"
              class="login-input"
            />
            <el-input
              v-model="email"
              placeholder="邮箱 (可选)"
              :prefix-icon="Message"
              size="large"
              class="login-input"
            />
            <el-input
              v-model="password"
              type="password"
              placeholder="密码 (至少6位)"
              :prefix-icon="Lock"
              size="large"
              class="login-input"
              show-password
            />
            <el-input
              v-model="tenantId"
              placeholder="租户ID (默认: default)"
              size="large"
              class="login-input"
            />
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleRegister"
            >
              注 册
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  padding: 24px;
}

.login-card {
  width: 420px;
  max-width: 100%;
  background: rgba(30, 41, 59, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
  padding: 40px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, #06b6d4, #3b82f6, #8b5cf6);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 32px rgba(6, 182, 212, 0.3);
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
  margin: 0 0 8px;
}

.login-subtitle {
  font-size: 14px;
  color: #94a3b8;
  margin: 0;
}

.login-tabs {
  margin-bottom: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 8px;
}

.login-input {
  width: 100%;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
  height: 48px;
  font-size: 16px;
  border-radius: 12px;
}
</style>
