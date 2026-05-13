<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import apiV2 from '@/services/api-v2'
import {
  Loading,
  Warning,
  CircleCheck,
  WarningFilled,
  CircleCheckFilled,
  Refresh,
  Timer,
  DataLine,
  Cpu,
  Collection,
  Share,
  MagicStick,
  ArrowRight,
  TrendCharts,
  InfoFilled
} from '@element-plus/icons-vue'

// 类型定义
interface ComponentHealth {
  name: string
  type: 'database' | 'llm' | 'message_queue' | 'cache' | 'file_system'
  status: 'healthy' | 'degraded' | 'unhealthy'
  latency_ms: number
  details: Record<string, any>
  last_check: number
  error?: string
}

interface HealthStatus {
  overall_status: string
  overall_status_code: number
  last_check: number
  components: Record<string, ComponentHealth>
  summary: {
    total: number
    healthy: number
    degraded: number
    unhealthy: number
  }
}

// 状态
const healthData = ref<HealthStatus | null>(null)
const loading = ref(false)
const refreshInterval = ref<number>()
const checking = ref(false)

// 状态配置
const statusConfig = {
  healthy: {
    icon: CircleCheckFilled,
    color: '#67c23a',
    label: '正常',
    bg: 'rgba(103, 194, 58, 0.15)',
    border: 'rgba(103, 194, 58, 0.3)',
    gradient: 'linear-gradient(135deg, #67c23a 0%, #95d475 100%)'
  },
  degraded: {
    icon: WarningFilled,
    color: '#e6a23c',
    label: '降级',
    bg: 'rgba(230, 162, 60, 0.15)',
    border: 'rgba(230, 162, 60, 0.3)',
    gradient: 'linear-gradient(135deg, #e6a23c 0%, #eebe77 100%)'
  },
  unhealthy: {
    icon: WarningFilled,
    color: '#f56c6c',
    label: '异常',
    bg: 'rgba(245, 108, 108, 0.15)',
    border: 'rgba(245, 108, 108, 0.3)',
    gradient: 'linear-gradient(135deg, #f56c6c 0%, #f89898 100%)'
  },
}

// 计算整体状态配置
const overallStatusConfig = computed(() => {
  const status = healthData.value?.overall_status || 'unhealthy'
  return statusConfig[status as keyof typeof statusConfig] || statusConfig.unhealthy
})

// 分组组件
const groupedComponents = computed(() => {
  if (!healthData.value) return {}

  const groups: Record<string, ComponentHealth[]> = {
    '数据库': [],
    'LLM 服务': [],
    '消息队列': [],
  }

  const typeMapping: Record<string, keyof typeof groups> = {
    database: '数据库',
    llm: 'LLM 服务',
    message_queue: '消息队列',
    cache: '数据库',
    file_system: '数据库',
  }

  Object.values(healthData.value.components).forEach((comp) => {
    const group = typeMapping[comp.type] || '数据库'
    groups[group].push(comp)
  })

  return groups
})

// 获取组件图标
const getComponentIcon = (type: string) => {
  const icons: Record<string, any> = {
    database: Collection,
    message_queue: Share,
    llm: MagicStick,
    cache: Cpu,
    file_system: DataLine
  }
  return icons[type] || Cpu
}

// 格式化时间
const formatTime = (timestamp: number) => {
  if (!timestamp) return '从未检查'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

// 获取状态文本
const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    healthy: '正常',
    degraded: '降级',
    unhealthy: '异常',
  }
  return texts[status] || status
}

// 获取状态样式类
const getStatusClass = (status: string) => {
  return `status-${status}`
}

// 获取延迟样式
const getLatencyClass = (latency: number) => {
  if (latency < 50) return 'latency-excellent'
  if (latency < 100) return 'latency-good'
  if (latency < 300) return 'latency-warning'
  return 'latency-bad'
}

// 获取健康检查
const fetchHealth = async (deepCheck: boolean = false) => {
  loading.value = true
  try {
    const response = await apiV2.getSystemHealth(deepCheck)
    healthData.value = response
  } catch (error) {
    console.error('获取健康状态失败:', error)
  } finally {
    loading.value = false
  }
}

// 检查单个组件
const checkComponent = async (componentName: string) => {
  checking.value = true
  try {
    await apiV2.getComponentHealth(componentName)
    await fetchHealth()
  } catch (error) {
    console.error(`检查组件 ${componentName} 失败:`, error)
  } finally {
    checking.value = false
  }
}

// 立即执行完整检查
const immediateCheck = async () => {
  checking.value = true
  try {
    await apiV2.immediateHealthCheck()
    await fetchHealth(true)
  } catch (error) {
    console.error('立即健康检查失败:', error)
  } finally {
    checking.value = false
  }
}

// 刷新状态
const refresh = async () => {
  await fetchHealth()
}

// 启动自动刷新
const startAutoRefresh = () => {
  refreshInterval.value = window.setInterval(() => {
    fetchHealth()
  }, 10000)
}

// 清理
const cleanup = () => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
}

// 生命周期
onMounted(() => {
  fetchHealth()
  startAutoRefresh()
})

onUnmounted(() => {
  cleanup()
})
</script>

<template>
  <div class="system-health-panel">
    <!-- 页面头部 -->
    <div class="panel-header">
      <div class="header-content">
        <div class="header-icon">
          <el-icon :size="24"><TrendCharts /></el-icon>
        </div>
        <div class="header-text">
          <h2 class="panel-title">系统健康状态</h2>
          <p class="panel-subtitle">系统组件运行状态和性能指标</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          @click="immediateCheck"
          :loading="checking"
          class="action-btn"
        >
          <el-icon><Refresh /></el-icon>
          <span>立即检查</span>
        </el-button>
        <el-button
          type="info"
          @click="refresh"
          :loading="loading"
          class="action-btn"
          plain
        >
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </div>

    <!-- 整体状态卡片 -->
    <div class="status-card" :class="getStatusClass(healthData?.overall_status || 'unhealthy')">
      <div class="status-glow" :style="{ background: overallStatusConfig.gradient }"></div>
      <div class="status-content">
        <div class="status-main">
          <div class="status-icon-wrapper" :style="{ background: overallStatusConfig.bg, borderColor: overallStatusConfig.border }">
            <el-icon :size="36" :color="overallStatusConfig.color">
              <component :is="overallStatusConfig.icon" />
            </el-icon>
          </div>
          <div class="status-info">
            <div class="status-label">系统整体状态</div>
            <div class="status-value" :style="{ color: overallStatusConfig.color }">
              {{ overallStatusConfig.label }}
            </div>
            <div class="status-time">
              <el-icon><Timer /></el-icon>
              <span>检查时间: {{ formatTime(healthData?.last_check || 0) }}</span>
            </div>
          </div>
        </div>

        <div class="status-summary">
          <div class="summary-item healthy">
            <div class="summary-value">{{ healthData?.summary.healthy || 0 }}</div>
            <div class="summary-label">正常</div>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-item degraded">
            <div class="summary-value">{{ healthData?.summary.degraded || 0 }}</div>
            <div class="summary-label">降级</div>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-item unhealthy">
            <div class="summary-value">{{ healthData?.summary.unhealthy || 0 }}</div>
            <div class="summary-label">异常</div>
          </div>
        </div>
      </div>
      <div class="status-bar" :style="{ background: overallStatusConfig.gradient }"></div>
    </div>

    <!-- 组件分组列表 -->
    <div class="components-section">
      <div
        v-for="(components, group) in groupedComponents"
        :key="group"
        class="component-group"
      >
        <div class="group-header">
          <div class="group-icon">
            <el-icon :size="18">
              <component :is="getComponentIcon(components[0]?.type || 'database')" />
            </el-icon>
          </div>
          <h3 class="group-title">{{ group }}</h3>
          <span class="group-count">{{ components.length }} 个组件</span>
        </div>

        <div class="components-list">
          <div
            v-for="component in components"
            :key="component.name"
            class="component-item"
            :class="getStatusClass(component.status)"
          >
            <div class="item-main">
              <div class="item-icon">
                <el-icon :size="18">
                  <component :is="getComponentIcon(component.type)" />
                </el-icon>
              </div>
              <div class="item-info">
                <div class="item-name">{{ component.name }}</div>
                <div class="item-type">{{ component.type }}</div>
              </div>
              <div class="item-status" :class="component.status">
                <el-icon v-if="component.status === 'healthy'"><CircleCheckFilled /></el-icon>
                <el-icon v-else-if="component.status === 'degraded'"><WarningFilled /></el-icon>
                <el-icon v-else><Warning /></el-icon>
                <span>{{ getStatusText(component.status) }}</span>
              </div>
            </div>

            <div class="item-metrics">
              <div class="metric latency" :class="getLatencyClass(component.latency_ms)">
                <el-icon><Timer /></el-icon>
                <span>{{ component.latency_ms }}ms</span>
              </div>
              <div class="metric time">
                <el-icon><DataLine /></el-icon>
                <span>{{ formatTime(component.last_check).split(' ')[1] || '--:--' }}</span>
              </div>
            </div>

            <div class="item-actions">
              <el-button
                type="primary"
                link
                size="small"
                @click="checkComponent(component.name)"
                :loading="checking"
              >
                <el-icon><Refresh /></el-icon>
                检查
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 警告提示 -->
    <div v-if="healthData?.summary?.unhealthy! > 0" class="warning-banner">
      <div class="warning-content">
        <div class="warning-icon">
          <el-icon><WarningFilled /></el-icon>
        </div>
        <div class="warning-text">
          <div class="warning-title">检测到异常组件</div>
          <div class="warning-desc">有 {{ healthData!.summary.unhealthy }} 个组件异常，请检查相关服务是否正常运行</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.system-health-panel {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  color: #e2e8f0;
}

/* Panel Header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(6, 182, 212, 0.1) 100%);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 12px;
  color: #38bdf8;
}

.panel-title {
  font-size: 20px;
  font-weight: 600;
  color: #f8fafc;
  margin: 0 0 2px 0;
}

.panel-subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  border-radius: 8px;
}

/* Status Card */
.status-card {
  position: relative;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 24px;
}

.status-card.status-healthy {
  border-left: 3px solid #67c23a;
}

.status-card.status-degraded {
  border-left: 3px solid #e6a23c;
}

.status-card.status-unhealthy {
  border-left: 3px solid #f56c6c;
}

.status-glow {
  position: absolute;
  top: -50%;
  right: -10%;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.12;
  pointer-events: none;
}

.status-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  position: relative;
  z-index: 1;
  gap: 24px;
}

.status-main {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-icon-wrapper {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 1px solid;
  flex-shrink: 0;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-label {
  font-size: 12px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-value {
  font-size: 28px;
  font-weight: 700;
}

.status-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.status-time .el-icon {
  font-size: 14px;
}

.status-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 50px;
}

.summary-item.healthy .summary-value { color: #67c23a; }
.summary-item.degraded .summary-value { color: #e6a23c; }
.summary-item.unhealthy .summary-value { color: #f56c6c; }

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
}

.summary-label {
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
}

.summary-divider {
  width: 1px;
  height: 30px;
  background: rgba(148, 163, 184, 0.15);
}

.status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
}

/* Components Section */
.components-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.component-group {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.08);
  border-radius: 14px;
  overflow: hidden;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: rgba(15, 23, 42, 0.4);
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.group-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.1);
  border-radius: 8px;
  color: #38bdf8;
}

.group-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
  margin: 0;
}

.group-count {
  font-size: 12px;
  color: #64748b;
  padding: 4px 10px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
}

.components-list {
  padding: 8px;
}

.component-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  transition: all 0.2s ease;
  border-left: 2px solid transparent;
}

.component-item:hover {
  background: rgba(56, 189, 248, 0.05);
}

.component-item.status-healthy {
  border-left-color: #67c23a;
}

.component-item.status-degraded {
  border-left-color: #e6a23c;
}

.component-item.status-unhealthy {
  border-left-color: #f56c6c;
}

.item-main {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 180px;
}

.item-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.1);
  border-radius: 8px;
  color: #38bdf8;
  flex-shrink: 0;
}

.item-info {
  flex: 1;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
  color: #f8fafc;
}

.item-type {
  font-size: 11px;
  color: #64748b;
  text-transform: capitalize;
}

.item-status {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.item-status.healthy {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.item-status.degraded {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
}

.item-status.unhealthy {
  background: rgba(245, 108, 108, 0.15);
  color: #f56c6c;
}

.item-metrics {
  display: flex;
  gap: 16px;
  min-width: 140px;
}

.metric {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94a3b8;
}

.metric .el-icon {
  font-size: 14px;
}

.metric.latency.latency-excellent { color: #67c23a; }
.metric.latency.latency-good { color: #95d475; }
.metric.latency.latency-warning { color: #e6a23c; }
.metric.latency.latency-bad { color: #f56c6c; }

.item-actions {
  min-width: 60px;
  text-align: right;
}

/* Warning Banner */
.warning-banner {
  margin-top: 20px;
  padding: 16px 20px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.2);
  border-radius: 12px;
}

.warning-content {
  display: flex;
  align-items: center;
  gap: 14px;
}

.warning-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(245, 108, 108, 0.15);
  border-radius: 10px;
  color: #f56c6c;
  font-size: 20px;
}

.warning-title {
  font-size: 14px;
  font-weight: 600;
  color: #f89898;
  margin-bottom: 2px;
}

.warning-desc {
  font-size: 13px;
  color: #94a3b8;
}

/* Responsive */
@media (max-width: 1024px) {
  .status-content {
    flex-direction: column;
    text-align: center;
    gap: 20px;
  }

  .status-main {
    flex-direction: column;
  }

  .status-summary {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .system-health-panel {
    padding: 16px;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .component-item {
    flex-wrap: wrap;
    gap: 12px;
  }

  .item-main {
    width: 100%;
  }

  .item-metrics {
    width: 100%;
    padding-left: 48px;
  }

  .item-actions {
    width: 100%;
    text-align: left;
    padding-left: 48px;
  }
}
</style>
