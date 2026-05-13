<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/configStore'
import { Setting, Refresh, InfoFilled, Check, Warning } from '@element-plus/icons-vue'

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
  <div class="config-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-icon">
        <el-icon :size="24"><Setting /></el-icon>
      </div>
      <div>
        <h1 class="page-title">配置管理中心</h1>
        <p class="page-desc">ConfigHub — 热加载配置管理与小说预设</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="reloadLoading" @click="handleReload">
          <el-icon class="mr-1"><Refresh /></el-icon>
          热加载配置
        </el-button>
      </div>
    </div>

    <!-- 热加载结果 -->
    <el-alert
      v-if="configStore.reloadResult"
      :title="configStore.reloadResult.message"
      :type="configStore.reloadResult.success ? 'success' : 'error'"
      :icon="configStore.reloadResult.success ? Check : Warning"
      closable
      class="result-alert"
    />

    <!-- 加载状态 -->
    <div v-if="configStore.loading" class="loading-section">
      <div class="glass-card loading-card">
        <el-skeleton :rows="6" animated />
      </div>
    </div>

    <!-- 配置概览 -->
    <div v-if="!configStore.loading && activeTab === 'overview' && configStore.fullConfig" class="config-grid">
      <div
        v-for="(value, key) in configStore.fullConfig"
        :key="key"
        class="glass-card config-card"
      >
        <div class="config-key">{{ key }}</div>
        <pre class="config-value">{{ formatValue(value) }}</pre>
      </div>
    </div>

    <!-- 小说预设 -->
    <div v-if="!configStore.loading && activeTab === 'presets'" class="presets-grid">
      <div
        v-for="preset in configStore.presets"
        :key="preset.name"
        class="glass-card preset-card"
      >
        <div class="preset-header">
          <span class="preset-title">{{ preset.title }}</span>
          <el-tag size="small" effect="dark">{{ preset.genre }}</el-tag>
        </div>
        <p class="preset-desc">{{ preset.description }}</p>
      </div>
      <div v-if="configStore.presets.length === 0" class="glass-card empty-card">
        <el-icon :size="32" color="#64748b"><InfoFilled /></el-icon>
        <p>暂无预设配置</p>
      </div>
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-if="configStore.error"
      :title="configStore.error"
      type="error"
      closable
      class="result-alert"
    />
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.config-dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

/* 页面标题 */
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.header-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 4px 15px rgba(6, 182, 212, 0.3);
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0;
  letter-spacing: -0.5px;
}

.page-desc {
  color: #94a3b8;
  font-size: 0.875rem;
  margin: 4px 0 0;
}

.header-actions {
  margin-left: auto;
}

/* 结果提示 */
.result-alert {
  margin-bottom: 20px;
}

/* 加载状态 */
.loading-section {
  margin-top: 20px;
}

.loading-card {
  padding: 24px;
}

/* 配置概览网格 */
.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.config-card {
  padding: 20px;
  transition: all 0.3s ease;
}

.config-card:hover {
  border-color: rgba(56, 189, 248, 0.3);
  transform: translateY(-1px);
}

.config-key {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: #06b6d4;
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.config-value {
  font-size: 0.8125rem;
  color: #e2e8f0;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* 小说预设网格 */
.presets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.preset-card {
  padding: 20px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.preset-card:hover {
  border-color: rgba(56, 189, 248, 0.3);
  transform: translateY(-2px);
}

.preset-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.preset-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #f8fafc;
}

.preset-desc {
  font-size: 0.875rem;
  color: #94a3b8;
  margin: 0;
  line-height: 1.6;
}

.empty-card {
  grid-column: 1 / -1;
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #64748b;
  font-size: 0.9375rem;
}
</style>
