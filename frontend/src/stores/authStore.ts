/* Pinia 认证状态管理 — Phase 1 多租户认证 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiV2 from '@/services/api-v2'

export interface UserInfo {
  id: string
  username: string
  email: string
  roles: string[]
}

export interface TenantInfo {
  id: string
  name: string
  tier: string
  features: string[]
}

export interface AuthState {
  user: UserInfo | null
  tenant: TenantInfo | null
  token: string
  isAuthenticated: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('ai_novels_jwt') || '')
  const user = ref<UserInfo | null>(null)
  const tenant = ref<TenantInfo | null>(null)

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  async function login(username: string, password: string, tenantId = 'default') {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    formData.append('tenant_id', tenantId)

    const resp: any = await apiV2.login(username, password, tenantId)
    token.value = resp.access_token
    user.value = resp.user
    tenant.value = resp.tenant
    localStorage.setItem('ai_novels_jwt', resp.access_token)
    return resp
  }

  async function register(username: string, password: string, email = '', tenantId = 'default') {
    const resp: any = await apiV2.register(username, email, password, tenantId)
    token.value = resp.access_token
    user.value = resp.user
    tenant.value = resp.tenant
    localStorage.setItem('ai_novels_jwt', resp.access_token)
    return resp
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const resp: any = await apiV2.getMe()
      user.value = resp
      tenant.value = resp.tenant
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    tenant.value = null
    localStorage.removeItem('ai_novels_jwt')
  }

  function initialize() {
    if (token.value) {
      fetchMe()
    }
  }

  return {
    token, user, tenant, isAuthenticated,
    login, register, fetchMe, logout, initialize,
  }
})
