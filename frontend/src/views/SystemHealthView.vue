<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import apiV2 from '@/services/api-v2'
import {
  OfficeBuilding,
  Connection,
  ChatLineRound,
  CircleCheck,
  Warning,
  CircleClose,
  Refresh,
  DataLine,
  Timer,
  Link,
  ArrowRight,
  Cpu,
  Collection,
  Share,
  MagicStick,
  Check,
  InfoFilled
} from '@element-plus/icons-vue'

interface ComponentHealth {
  name: string
  type: string
  status: 'healthy' | 'degraded' | 'unhealthy'
  latency_ms: number
  details: Record<string, any>
  last_check: number
  error?: string
}

interface SystemHealthResponse {
  overall_status: string
  overall_status_code: number
  components: Record<string, ComponentHealth>
  last_check: number
  component_count: number
  healthy_count: number
  degraded_count: number
  unhealthy_count: number
  connections?: Record<string, any>
}

const loading = ref(false)
const components = ref<Record<string, ComponentHealth>>({})
const overallStatus = ref<string>('unknown')
const healthyCount = ref(0)
const degradedCount = ref(0)
const unhealthyCount = ref(0)
const lastCheck = ref<number>(0)
const connections = ref<Record<string, any>>({})

// 状态配置
const statusConfig = {
  healthy: {
    text: '系统正常',
    subtext: '所有组件正常运行',
    color: '#67c23a',
    bg: 'rgba(103, 194, 58, 0.15)',
    border: 'rgba(103, 194, 58, 0.3)',
    icon: CircleCheck,
    gradient: 'linear-gradient(135deg, #67c23a 0%, #95d475 100%)'
  },
  degraded: {
    text: '部分降级',
    subtext: '部分组件运行异常',
    color: '#e6a23c',
    bg: 'rgba(230, 162, 60, 0.15)',
    border: 'rgba(230, 162, 60, 0.3)',
    icon: Warning,
    gradient: 'linear-gradient(135deg, #e6a23c 0%, #eebe77 100%)'
  },
  unhealthy: {
    text: '系统故障',
    subtext: '有组件出现故障',
    color: '#f56c6c',
    bg: 'rgba(245, 108, 108, 0.15)',
    border: 'rgba(245, 108, 108, 0.3)',
    icon: CircleClose,
    gradient: 'linear-gradient(135deg, #f56c6c 0%, #f89898 100%)'
  },
  unknown: {
    text: '未知状态',
    subtext: '尚未获取状态信息',
    color: '#909399',
    bg: 'rgba(144, 147, 153, 0.15)',
    border: 'rgba(144, 147, 153, 0.3)',
    icon: InfoFilled,
    gradient: 'linear-gradient(135deg, #909399 0%, #b1b3b8 100%)'
  }
}

const currentStatus = computed(() => statusConfig[overallStatus.value as keyof typeof statusConfig] || statusConfig.unknown)

const allComponents = computed(() => Object.values(components.value))

// 分组组件
const groupedComponents = computed(() => {
  const groups: Record<string, ComponentHealth[]> = {
    '数据库': [],
    '消息队列': [],
    'LLM 服务': []
  }

  const typeMapping: Record<string, keyof typeof groups> = {
    database: '数据库',
    message_queue: '消息队列',
    llm: 'LLM 服务'
  }

  Object.values(components.value).forEach((comp) => {
    const group = typeMapping[comp.type] || '数据库'
    groups[group].push(comp)
  })

  return groups
})

const checkSystemHealth = async () => {
  loading.value = true
  try {
    const response = await apiV2.getSystemHealthFull(true)
    if (response) {
      overallStatus.value = response.overall_status || 'unknown'

      // 后端返回 components[name] = ComponentHealth dict (含 type/latency_ms/last_check)
      const flatComponents: Record<string, ComponentHealth> = {}
      if (response.components) {
        for (const [name, comp] of Object.entries(response.components)) {
          if (comp && typeof comp === 'object') {
            const ch = comp as any
            // 兼容新旧格式
            if (ch.type) {
              flatComponents[name] = ch as ComponentHealth
            } else if (ch.status && typeof ch.status === 'object') {
              flatComponents[name] = { name, ...ch.status } as ComponentHealth
            } else {
              flatComponents[name] = { name, status: ch.status || 'unknown', type: '', latency_ms: 0, details: {}, last_check: 0 }
            }
          }
        }
      }
      components.value = flatComponents

      healthyCount.value = Object.values(flatComponents).filter(c => c.status === 'healthy').length
      degradedCount.value = Object.values(flatComponents).filter(c => c.status === 'degraded').length
      unhealthyCount.value = Object.values(flatComponents).filter(c => c.status === 'unhealthy').length
      lastCheck.value = response.last_check || Date.now() / 1000
      connections.value = response.connections || {}
    }
  } catch (error) {
    console.error('检查系统健康状态失败:', error)
  } finally {
    loading.value = false
  }
}

const checkComponent = async (componentName: string) => {
  loading.value = true
  try {
    const response = await apiV2.getComponentHealth(componentName)
    if (response) {
      // 后端返回 ComponentHealth dict (含 type/latency_ms/last_check)
      components.value[componentName] = {
        name: componentName,
        status: response.status || 'unknown',
        type: response.type || '',
        latency_ms: response.latency_ms || 0,
        details: response.details || {},
        last_check: response.last_check || 0,
        error: response.error,
      } as ComponentHealth
    }
  } catch (error) {
    console.error(`检查组件 ${componentName} 状态失败:`, error)
  } finally {
    loading.value = false
  }
}

const getComponentName = (name: string) => {
  const names: Record<string, string> = {
    mysql: 'MySQL',
    neo4j: 'Neo4j',
    mongodb: 'MongoDB',
    chromadb: 'ChromaDB',
    rocketmq_producer: 'RocketMQ',
    rocketmq_consumer: 'RocketMQ Consumer',
    ollama: 'Ollama LLM',
  }
  return names[name] || name
}

const getComponentType = (type: string) => {
  const types: Record<string, string> = {
    database: '数据库',
    message_queue: '消息队列',
    llm: 'LLM 服务',
  }
  return types[type] || type
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    healthy: '正常',
    degraded: '降级',
    unhealthy: '故障',
  }
  return texts[status] || '未知'
}

const getComponentStatus = (name: string) => {
  const component = components.value[name]
  if (!component) {
    return { status: 'info', text: '未检查' }
  }
  const statusMap: Record<string, { status: string; text: string }> = {
    healthy: { status: 'success', text: '正常' },
    degraded: { status: 'warning', text: '降级' },
    unhealthy: { status: 'danger', text: '故障' },
  }
  return statusMap[component.status] || { status: 'info', text: '未知' }
}

const formatTimestamp = (timestamp: number) => {
  if (!timestamp) return '从未检查'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

// 获取组件图标
const getComponentIcon = (type: string) => {
  const icons: Record<string, any> = {
    database: Collection,
    message_queue: Share,
    llm: MagicStick
  }
  return icons[type] || Cpu
}

// 获取延迟样式
const getLatencyClass = (latency: number) => {
  if (latency < 50) return 'latency-excellent'
  if (latency < 100) return 'latency-good'
  if (latency < 300) return 'latency-warning'
  return 'latency-bad'
}

// 连接信息配置
const connectionConfigs = [
  {
    key: 'mysql',
    title: 'MySQL 数据库',
    icon: Collection,
    color: '#409eff',
    fields: [
      { key: 'host', label: '主机', default: 'localhost' },
      { key: 'port', label: '端口', default: 3307 },
      { key: 'database', label: '数据库', default: 'ai_novels' }
    ]
  },
  {
    key: 'neo4j',
    title: 'Neo4j 图数据库',
    icon: Share,
    color: '#008cc1',
    fields: [
      { key: 'uri', label: 'URI', default: 'bolt://localhost:7687' },
      { key: 'user', label: '用户名', default: 'neo4j' },
      { key: 'database', label: '数据库', default: 'neo4j' }
    ]
  },
  {
    key: 'mongodb',
    title: 'MongoDB 文档数据库',
    icon: DataLine,
    color: '#47A248',
    fields: [
      { key: 'host', label: '主机', default: 'localhost' },
      { key: 'port', label: '端口', default: 27017 },
      { key: 'auth_source', label: '认证数据库', default: 'admin' }
    ]
  },
  {
    key: 'chromadb',
    title: 'ChromaDB 向量数据库',
    icon: MagicStick,
    color: '#424242',
    fields: [
      { key: 'host', label: '主机', default: 'localhost' },
      { key: 'port', label: '端口', default: 8000 },
      { key: 'persist_dir', label: '持久化路径', default: './chroma_db' }
    ]
  },
  {
    key: 'rocketmq',
    title: 'RocketMQ 消息队列',
    icon: Connection,
    color: '#9254de',
    fields: [
      { key: 'name_server', label: 'Name Server', default: 'localhost:9876' },
      { key: 'group_name', label: 'Producer组', default: 'ai_novels_producer' }
    ]
  }
]

onMounted(() => {
  checkSystemHealth()
})
</script>

<template>
  <div class="system-health-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-icon">
          <el-icon :size="28"><Cpu /></el-icon>
        </div>
        <div class="header-text">
          <h1 class="page-title">系统组件监控</h1>
          <p class="page-description">实时监控 MySQL、MongoDB、Neo4j、ChromaDB、RocketMQ 等组件运行状态</p>
        </div>
      </div>
      <el-button
        type="primary"
        @click="checkSystemHealth"
        :loading="loading"
        class="refresh-btn"
      >
        <el-icon v-if="!loading" :size="16"><Refresh /></el-icon>
        <span>{{ loading ? '刷新中...' : '刷新状态' }}</span>
      </el-button>
    </div>

    <!-- 整体状态卡片 -->
    <div class="status-hero" :style="{ '--status-color': currentStatus.color }">
      <div class="status-glow" :style="{ background: currentStatus.gradient }"></div>
      <div class="status-content">
        <div class="status-main">
          <div class="status-icon-wrapper" :style="{ background: currentStatus.bg, borderColor: currentStatus.border }">
            <el-icon :size="40" :color="currentStatus.color">
              <component :is="currentStatus.icon" />
            </el-icon>
          </div>
          <div class="status-info">
            <div class="status-label">系统整体状态</div>
            <div class="status-value" :style="{ color: currentStatus.color }">{{ currentStatus.text }}</div>
            <div class="status-sub">{{ currentStatus.subtext }}</div>
          </div>
        </div>
        <div class="status-divider"></div>
        <div class="status-stats">
          <div class="stat-box healthy">
            <div class="stat-icon"><el-icon><CircleCheck /></el-icon></div>
            <div class="stat-number">{{ healthyCount }}</div>
            <div class="stat-label">正常</div>
          </div>
          <div class="stat-box degraded">
            <div class="stat-icon"><el-icon><Warning /></el-icon></div>
            <div class="stat-number">{{ degradedCount }}</div>
            <div class="stat-label">降级</div>
          </div>
          <div class="stat-box unhealthy">
            <div class="stat-icon"><el-icon><CircleClose /></el-icon></div>
            <div class="stat-number">{{ unhealthyCount }}</div>
            <div class="stat-label">故障</div>
          </div>
        </div>
      </div>
      <div class="status-bar" :style="{ background: currentStatus.gradient }"></div>
    </div>

    <!-- 组件状态网格 -->
    <div class="components-section">
      <div class="section-header">
        <div class="section-icon">
          <el-icon><OfficeBuilding /></el-icon>
        </div>
        <div class="section-title-group">
          <h2 class="section-title">组件状态</h2>
          <p class="section-subtitle">各组件实时运行状态监控</p>
        </div>
      </div>

      <div class="components-grid">
        <div
          v-for="component in allComponents"
          :key="component.name"
          class="component-card"
          :class="`status-${component.status}`"
        >
          <div class="card-header">
            <div class="component-icon" :class="component.type">
              <el-icon :size="22">
                <component :is="getComponentIcon(component.type)" />
              </el-icon>
            </div>
            <div class="component-meta">
              <div class="component-name">{{ getComponentName(component.name) }}</div>
              <div class="component-type">{{ getComponentType(component.type) }}</div>
            </div>
            <div class="component-status-badge" :class="component.status">
              <el-icon v-if="component.status === 'healthy'"><Check /></el-icon>
              <el-icon v-else-if="component.status === 'degraded'"><Warning /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
              <span>{{ getStatusText(component.status) }}</span>
            </div>
          </div>

          <div class="card-body">
            <div class="metric-row">
              <div class="metric">
                <div class="metric-icon"><el-icon><Timer /></el-icon></div>
                <div class="metric-content">
                  <div class="metric-label">响应延迟</div>
                  <div class="metric-value" :class="getLatencyClass(component.latency_ms)">
                    {{ component.latency_ms }}<span class="unit">ms</span>
                  </div>
                </div>
              </div>
              <div class="metric">
                <div class="metric-icon"><el-icon><Link /></el-icon></div>
                <div class="metric-content">
                  <div class="metric-label">最后检查</div>
                  <div class="metric-value time">{{ formatTimestamp(component.last_check).split(' ')[1] || '--:--' }}</div>
                </div>
              </div>
            </div>

            <div v-if="component.error" class="error-message">
              <el-icon><Warning /></el-icon>
              <span>{{ component.error }}</span>
            </div>
          </div>

          <div class="card-footer">
            <el-button
              size="small"
              type="primary"
              text
              @click="checkComponent(component.name)"
              :loading="loading"
            >
              <el-icon v-if="!loading"><Refresh /></el-icon>
              {{ loading ? '检查中' : '重新检查' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 连接信息面板 -->
    <div class="connections-section">
      <div class="section-header">
        <div class="section-icon">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="section-title-group">
          <h2 class="section-title">连接信息</h2>
          <p class="section-subtitle">各组件连接配置详情</p>
        </div>
      </div>

      <div class="connections-grid">
        <div
          v-for="config in connectionConfigs"
          :key="config.key"
          class="connection-card"
        >
          <div class="connection-header" :style="{ '--connection-color': config.color }">
            <div class="connection-icon" :style="{ background: `${config.color}15`, color: config.color }">
              <el-icon :size="20"><component :is="config.icon" /></el-icon>
            </div>
            <div class="connection-title-group">
              <div class="connection-title">{{ config.title }}</div>
              <el-tag
                :type="getComponentStatus(config.key).status"
                size="small"
                effect="light"
                class="connection-status"
              >
                {{ getComponentStatus(config.key).text }}
              </el-tag>
            </div>
          </div>

          <div class="connection-body">
            <div
              v-for="field in config.fields"
              :key="field.key"
              class="connection-field"
            >
              <span class="field-label">{{ field.label }}</span>
              <span class="field-value">{{ connections[config.key]?.[field.key] || field.default }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.system-health-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px 24px;
  color: #e2e8f0;
}

/* Page Header */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32px;
  gap: 20px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(6, 182, 212, 0.1) 100%);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 14px;
  color: #38bdf8;
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 26px;
  font-weight: 600;
  color: #f8fafc;
  margin: 0;
}

.page-description {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 10px;
  font-weight: 500;
}

/* Status Hero */
.status-hero {
  position: relative;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 20px;
  overflow: hidden;
  margin-bottom: 32px;
}

.status-glow {
  position: absolute;
  top: -50%;
  right: -10%;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
  pointer-events: none;
}

.status-content {
  display: flex;
  align-items: center;
  padding: 32px;
  gap: 48px;
  position: relative;
  z-index: 1;
}

.status-main {
  display: flex;
  align-items: center;
  gap: 20px;
  flex: 1;
}

.status-icon-wrapper {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  border: 1px solid;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-label {
  font-size: 13px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-value {
  font-size: 32px;
  font-weight: 700;
}

.status-sub {
  font-size: 14px;
  color: #94a3b8;
}

.status-divider {
  width: 1px;
  height: 80px;
  background: rgba(148, 163, 184, 0.15);
}

.status-stats {
  display: flex;
  gap: 24px;
}

.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
  min-width: 80px;
}

.stat-box.healthy .stat-icon { color: #67c23a; }
.stat-box.degraded .stat-icon { color: #e6a23c; }
.stat-box.unhealthy .stat-icon { color: #f56c6c; }

.stat-box.healthy .stat-number { color: #67c23a; }
.stat-box.degraded .stat-number { color: #e6a23c; }
.stat-box.unhealthy .stat-number { color: #f56c6c; }

.stat-icon {
  font-size: 20px;
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.status-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
}

/* Section */
.components-section,
.connections-section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.section-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 10px;
  color: #38bdf8;
}

.section-title-group {
  flex: 1;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #f8fafc;
  margin: 0 0 2px 0;
}

.section-subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

/* Components Grid */
.components-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.component-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.component-card:hover {
  background: rgba(30, 41, 59, 0.7);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.component-card.status-healthy {
  border-left: 3px solid #67c23a;
}

.component-card.status-degraded {
  border-left: 3px solid #e6a23c;
}

.component-card.status-unhealthy {
  border-left: 3px solid #f56c6c;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.component-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  flex-shrink: 0;
}

.component-icon.database {
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
}

.component-icon.message_queue {
  background: rgba(146, 84, 222, 0.15);
  color: #9254de;
}

.component-icon.llm {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.component-meta {
  flex: 1;
}

.component-name {
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
}

.component-type {
  font-size: 12px;
  color: #64748b;
}

.component-status-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.component-status-badge.healthy {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.component-status-badge.degraded {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
}

.component-status-badge.unhealthy {
  background: rgba(245, 108, 108, 0.15);
  color: #f56c6c;
}

.card-body {
  padding: 16px;
}

.metric-row {
  display: flex;
  gap: 16px;
}

.metric {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.4);
  border-radius: 10px;
}

.metric-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.1);
  border-radius: 8px;
  color: #38bdf8;
}

.metric-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: #f8fafc;
}

.metric-value .unit {
  font-size: 12px;
  color: #64748b;
  margin-left: 2px;
}

.metric-value.latency-excellent { color: #67c23a; }
.metric-value.latency-good { color: #95d475; }
.metric-value.latency-warning { color: #e6a23c; }
.metric-value.latency-bad { color: #f56c6c; }

.metric-value.time {
  font-size: 14px;
  color: #94a3b8;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.2);
  border-radius: 8px;
  font-size: 12px;
  color: #f89898;
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}

/* Connections Grid */
.connections-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.connection-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 14px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.connection-card:hover {
  background: rgba(30, 41, 59, 0.7);
  border-color: rgba(148, 163, 184, 0.2);
  transform: translateY(-2px);
}

.connection-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.connection-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  flex-shrink: 0;
}

.connection-title-group {
  flex: 1;
}

.connection-title {
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 4px;
}

.connection-status {
  font-size: 11px;
}

.connection-body {
  padding: 12px 16px;
}

.connection-field {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.05);
}

.connection-field:last-child {
  border-bottom: none;
}

.field-label {
  font-size: 12px;
  color: #64748b;
}

.field-value {
  font-size: 12px;
  color: #94a3b8;
  font-family: 'Monaco', 'Menlo', monospace;
}

/* Responsive */
@media (max-width: 1024px) {
  .status-content {
    flex-direction: column;
    gap: 24px;
    text-align: center;
  }

  .status-divider {
    width: 100%;
    height: 1px;
  }

  .status-stats {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .system-health-view {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .status-content {
    padding: 24px;
  }

  .status-main {
    flex-direction: column;
  }

  .status-stats {
    flex-wrap: wrap;
  }

  .components-grid,
  .connections-grid {
    grid-template-columns: 1fr;
  }

  .metric-row {
    flex-direction: column;
  }
}
</style>
