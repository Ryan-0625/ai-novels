<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/configStore'

const configStore = useConfigStore()
const activeTab = ref('overview')
const reloadLoading = ref(false)

onMounted(() => {
  configStore.fetchFullConfig()
  configStore.fetchPresets()
})

async function handleReload() {
  reloadLoading.value = true
  await configStore.reloadConfig()
  reloadLoading.value = false
}

function formatValue(v: any): string {
  if (v === null) return 'null'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}
</script>

<template>
  <div class="config-dashboard p-4">
    <h2 class="text-2xl font-bold text-white mb-4">配置管理中心 (ConfigHub)</h2>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 概览 -->
      <el-tab-pane label="配置概览" name="overview">
        <el-button type="primary" :loading="reloadLoading" @click="handleReload" class="mb-4">
          热加载配置
        </el-button>
        <el-alert
          v-if="configStore.reloadResult"
          :title="configStore.reloadResult.message"
          :type="configStore.reloadResult.success ? 'success' : 'error'"
          closable
          class="mb-4"
        />
        <el-descriptions v-if="configStore.fullConfig" :column="2" border>
          <el-descriptions-item
            v-for="(value, key) in configStore.fullConfig"
            :key="key"
            :label="key"
          >
            <pre class="text-xs">{{ formatValue(value) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <!-- 小说预设 -->
      <el-tab-pane label="小说预设" name="presets">
        <el-row :gutter="16">
          <el-col v-for="preset in configStore.presets" :key="preset.name" :span="8" class="mb-4">
            <el-card shadow="hover">
              <template #header>
                <span class="font-bold">{{ preset.title }}</span>
                <el-tag size="small" class="ml-2">{{ preset.genre }}</el-tag>
              </template>
              <p class="text-slate-300 text-sm">{{ preset.description }}</p>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-dashboard {
  background: #0b1120;
  min-height: 100vh;
}
</style>
