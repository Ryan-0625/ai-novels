/* Pinia 配置状态管理 (Step 12/13) */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiV2, { type NovelPreset, type ConfigReloadResponse } from '@/services/api-v2'

export const useConfigStore = defineStore('config', () => {
  const fullConfig = ref<Record<string, any> | null>(null)
  const presets = ref<NovelPreset[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const reloadResult = ref<ConfigReloadResponse | null>(null)

  async function fetchFullConfig() {
    loading.value = true
    error.value = null
    try {
      fullConfig.value = await apiV2.getFullConfig()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch config'
    } finally {
      loading.value = false
    }
  }

  async function fetchPresets() {
    loading.value = true
    error.value = null
    try {
      presets.value = await apiV2.listNovelPresets()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch presets'
    } finally {
      loading.value = false
    }
  }

  async function reloadConfig() {
    loading.value = true
    error.value = null
    try {
      reloadResult.value = await apiV2.reloadConfig()
    } catch (e: any) {
      error.value = e.message || 'Failed to reload config'
    } finally {
      loading.value = false
    }
  }

  async function getConfigItem(keyPath: string): Promise<any> {
    try {
      const resp = await apiV2.getConfigItem(keyPath)
      return resp.value
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  return {
    fullConfig, presets, loading, error, reloadResult,
    fetchFullConfig, fetchPresets, reloadConfig, getConfigItem,
  }
})
