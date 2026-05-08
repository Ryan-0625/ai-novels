<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import apiV2, { connectSSE, type SSEEvent } from '@/services/api-v2'
import { logError } from '@/utils/logger'
import GenerationMonitor from '@/components/GenerationMonitor.vue'
import AgentActivityFeed from '@/components/AgentActivityFeed.vue'
import type { ActivityItem } from '@/components/AgentActivityFeed.vue'
import { Refresh, Loading, SuccessFilled, Warning, CircleCheck, View, Close } from '@element-plus/icons-vue'

// 类型定义
interface Task {
  task_id: string
  agent_name?: string
  user_id?: string
  task_type?: string
  genre?: string
  title?: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  current_stage?: string
  created_at?: string
  started_at?: string
  completed_at?: string
  error?: string
}

interface CurrentActivity {
  agentName: string
  stage: string
  progress: number
  timestamp: number
}

// 状态
const tasks = ref<Task[]>([])
const loading = ref(false)
const refreshInterval = ref<number>()
const selectedTask = ref<Task | null>(null)

// SSE 状态
const sseConnected = ref(false)
const currentActivity = ref<CurrentActivity | null>(null)
const llmCall = ref<{ provider: string; model: string; status: 'requesting' | 'streaming' | 'done' | 'error' } | null>(null)
const activities = ref<ActivityItem[]>([])
let disconnectSSE: (() => void) | null = null

// 路由
const router = useRouter()

// 状态颜色映射
const statusColors: Record<string, string> = {
  pending: '#f59e0b',
  running: '#06b6d4',
  completed: '#10b981',
  failed: '#ef4444',
  cancelled: '#64748b',
}

// 状态文本映射
const statusText: Record<string, string> = {
  pending: '待处理',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

// 状态图标映射
const statusIcons: Record<string, any> = {
  pending: CircleCheck,
  running: Loading,
  completed: SuccessFilled,
  failed: Warning,
  cancelled: Close,
}

// 获取任务列表（v2 API）
const fetchTasks = async () => {
  loading.value = true
  try {
    const response = await apiV2.listTasks()
    tasks.value = (response.tasks || []).map((t: any) => ({
      ...t,
      status: t.status || 'pending',
      progress: t.progress || 0,
    }))
  } catch (error) {
    logError('获取任务列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取任务详细状态（v2 API）
const fetchTaskStatus = async (taskId: string) => {
  try {
    return await apiV2.getTask(taskId)
  } catch (error) {
    logError(`获取任务 ${taskId} 状态失败:`, error)
    return null
  }
}

// 取消任务（v2 API）
const cancelTask = async (taskId: string) => {
  try {
    await apiV2.taskAction(taskId, 'cancel')
    await fetchTasks()
  } catch (error) {
    logError(`取消任务 ${taskId} 失败:`, error)
  }
}

// 查看任务
const viewTask = (task: Task) => {
  selectedTask.value = task
  router.push(`/tasks/preview/${task.task_id}`).catch(err => {
    console.error('路由跳转失败:', err)
  })
}

// 刷新任务状态
const refreshStatus = async () => {
  await fetchTasks()
}

// 启动自动刷新
const startAutoRefresh = () => {
  refreshInterval.value = window.setInterval(() => {
    refreshStatus()
  }, 5000)
}

// 清理
const cleanup = () => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
  if (disconnectSSE) {
    disconnectSSE()
    disconnectSSE = null
  }
}

// SSE 事件处理
function handleSSEEvent(event: SSEEvent) {
  const payload = event.payload || {}
  const agentName = payload.agent_name || event.source || 'unknown'

  switch (event.type) {
    case 'task.created':
      fetchTasks()
      break
    case 'agent.started':
    case 'task.started':
      currentActivity.value = {
        agentName,
        stage: payload.stage || '执行中',
        progress: payload.progress || 0.1,
        timestamp: Date.now(),
      }
      activities.value.push({
        id: `${agentName}-${Date.now()}`,
        agentName,
        stage: payload.stage || '执行中',
        status: 'running',
        timestamp: Date.now(),
      })
      break
    case 'llm.request':
      llmCall.value = {
        provider: payload.provider || 'ollama',
        model: payload.model || 'qwen2.5-7b',
        status: 'requesting',
      }
      break
    case 'llm.response':
      llmCall.value = {
        provider: payload.provider || 'ollama',
        model: payload.model || 'qwen2.5-7b',
        status: 'done',
      }
      break
    case 'llm.stream.chunk':
      if (llmCall.value && llmCall.value.status !== 'done') {
        llmCall.value.status = 'streaming'
      }
      break
    case 'agent.completed':
    case 'task.completed':
      currentActivity.value = {
        agentName,
        stage: payload.stage || '完成',
        progress: 1,
        timestamp: Date.now(),
      }
      // 更新对应活动为 completed
      {
        const idx = activities.value.findIndex(
          a => a.agentName === agentName && a.status === 'running'
        )
        if (idx >= 0) {
          activities.value[idx].status = 'completed'
          activities.value[idx].duration = Date.now() - activities.value[idx].timestamp
        }
      }
      setTimeout(() => {
        if (currentActivity.value?.agentName === agentName) {
          currentActivity.value = null
        }
        llmCall.value = null
      }, 2000)
      fetchTasks()
      break
    case 'agent.failed':
    case 'task.failed':
      {
        const idx = activities.value.findIndex(
          a => a.agentName === agentName && a.status === 'running'
        )
        if (idx >= 0) {
          activities.value[idx].status = 'failed'
          activities.value[idx].duration = Date.now() - activities.value[idx].timestamp
          activities.value[idx].details = { error: payload.error || '未知错误' }
        }
      }
      llmCall.value = null
      fetchTasks()
      break
  }
}

// 生命周期钩子
onMounted(() => {
  fetchTasks()
  startAutoRefresh()
  disconnectSSE = connectSSE(
    handleSSEEvent,
    () => { sseConnected.value = false },
    () => { sseConnected.value = true },
  )
})

onUnmounted(() => {
  cleanup()
})

// 计算属性
const pendingTasks = computed(() => tasks.value.filter(t => t.status === 'pending'))
const runningTasks = computed(() => tasks.value.filter(t => t.status === 'running'))
const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'))
const failedTasks = computed(() => tasks.value.filter(t => t.status === 'failed'))

// 统计卡片数据
const statCards = computed(() => [
  {
    label: '待处理',
    value: pendingTasks.value.length,
    icon: CircleCheck,
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.15)'
  },
  {
    label: '进行中',
    value: runningTasks.value.length,
    icon: Loading,
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.15)'
  },
  {
    label: '已完成',
    value: completedTasks.value.length,
    icon: SuccessFilled,
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.15)'
  },
  {
    label: '失败',
    value: failedTasks.value.length,
    icon: Warning,
    color: '#ef4444',
    bgColor: 'rgba(239, 68, 68, 0.15)'
  },
])
</script>

<template>
  <div class="task-monitor-view">
    <!-- 页面头部 -->
    <div class="page-header animate-fade-in">
      <div class="header-content">
        <div class="header-icon">
          <el-icon :size="28"><Monitor /></el-icon>
        </div>
        <div class="header-text">
          <h1 class="page-title">任务监控</h1>
          <p class="page-description">实时监控小说生成任务的进度和状态</p>
        </div>
      </div>
      <el-button 
        type="primary" 
        @click="fetchTasks" 
        :loading="loading" 
        class="refresh-btn"
        circle
      >
        <el-icon :size="18"><Refresh /></el-icon>
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid animate-fade-in" style="animation-delay: 0.1s">
      <div
        v-for="(card, index) in statCards"
        :key="card.label"
        class="stat-card"
        :style="{ animationDelay: `${0.1 + index * 0.05}s` }"
      >
        <div class="stat-icon-wrapper" :style="{ background: card.bgColor }">
          <el-icon :size="24" :style="{ color: card.color }">
            <component :is="card.icon" />
          </el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
        <div class="stat-glow" :style="{ background: card.color }"></div>
      </div>
    </div>

    <!-- 实时监控面板 -->
    <div class="monitor-grid animate-fade-in" style="animation-delay: 0.25s">
      <div class="monitor-col">
        <GenerationMonitor
          :is-connected="sseConnected"
          :current-activity="currentActivity"
          :llm-call="llmCall"
          recent-output=""
        />
      </div>
      <div class="monitor-col">
        <AgentActivityFeed :activities="activities" />
      </div>
    </div>

    <!-- 任务列表卡片 -->
    <div class="glass-card task-list-card animate-fade-in" style="animation-delay: 0.3s">
      <div class="card-header">
        <div class="card-title-section">
          <span class="card-title">任务列表</span>
          <span class="task-count">{{ tasks.length }} 个任务</span>
        </div>
        <div class="card-actions">
          <el-radio-group v-model="filterStatus" size="small" class="filter-group">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="running">进行中</el-radio-button>
            <el-radio-button value="completed">已完成</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div class="task-table-wrapper">
        <el-table
          v-loading="loading"
          :data="tasks"
          class="task-table"
          :header-cell-style="{ 
            background: 'transparent', 
            color: '#94a3b8', 
            fontWeight: 600,
            borderBottom: '1px solid rgba(255,255,255,0.1)'
          }"
          :cell-style="{ 
            background: 'transparent',
            borderBottom: '1px solid rgba(255,255,255,0.05)'
          }"
        >
          <el-table-column prop="task_id" label="任务ID" width="140">
            <template #default="{ row }">
              <span class="task-id">{{ row.task_id.slice(-8) }}</span>
            </template>
          </el-table-column>
          
          <el-table-column prop="title" label="标题" min-width="200">
            <template #default="{ row }">
              <div class="task-title">
                <span class="title-text">{{ row.title || '未命名任务' }}</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="genre" label="类型" width="100">
            <template #default="{ row }">
              <span class="genre-tag">{{ row.genre }}</span>
            </template>
          </el-table-column>
          
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <div class="status-badge" :class="`status-${row.status}`">
                <span class="status-dot"></span>
                <span>{{ statusText[row.status] }}</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="progress" label="进度" width="180">
            <template #default="{ row }">
              <div class="progress-wrapper">
                <div class="progress-bar">
                  <div 
                    class="progress-fill" 
                    :style="{ 
                      width: `${row.progress}%`,
                      background: statusColors[row.status]
                    }"
                  ></div>
                </div>
                <span class="progress-text">{{ row.progress }}%</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="created_at" label="创建时间" width="160">
            <template #default="{ row }">
              <span class="time-text">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</span>
            </template>
          </el-table-column>
          
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <div class="action-buttons">
                <el-button
                  v-if="row.status === 'running' || row.status === 'completed'"
                  type="primary"
                  size="small"
                  class="action-btn view-btn"
                  @click="viewTask(row)"
                >
                  <el-icon :size="14"><View /></el-icon>
                </el-button>
                <el-button
                  v-if="row.status === 'pending' || row.status === 'running'"
                  type="danger"
                  size="small"
                  class="action-btn cancel-btn"
                  @click="cancelTask(row.task_id)"
                >
                  <el-icon :size="14"><Close /></el-icon>
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Monitor } from '@element-plus/icons-vue'

export default {
  name: 'TaskMonitorView',
  components: {
    Monitor
  },
  data() {
    return {
      filterStatus: 'all'
    }
  }
}
</script>

<style scoped>
@import '@/styles/glassmorphism.css';

.task-monitor-view {
  max-width: 1400px;
  margin: 0 auto;
}

.monitor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

@media (max-width: 1024px) {
  .monitor-grid {
    grid-template-columns: 1fr;
  }
}

/* Animations */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fadeIn 0.6s ease forwards;
}

/* Page Header */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 30px rgba(139, 92, 246, 0.3);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0;
  letter-spacing: -0.5px;
}

.page-description {
  font-size: 1rem;
  color: #94a3b8;
  margin: 0;
}

.refresh-btn {
  width: 48px;
  height: 48px;
  background: rgba(139, 92, 246, 0.15) !important;
  border: 1px solid rgba(139, 92, 246, 0.3) !important;
  color: #a855f7 !important;
  transition: all 0.3s ease;
}

.refresh-btn:hover {
  background: rgba(139, 92, 246, 0.25) !important;
  transform: rotate(180deg);
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.stat-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  font-size: 0.875rem;
  color: #94a3b8;
}

.stat-glow {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

.stat-card:hover .stat-glow {
  opacity: 1;
}

/* Glass Card */
.glass-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
}

/* Task List Card */
.task-list-card {
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.card-title-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #f8fafc;
}

.task-count {
  font-size: 0.8125rem;
  color: #64748b;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 10px;
  border-radius: 20px;
}

/* Filter Group */
.filter-group :deep(.el-radio-button__inner) {
  background: rgba(15, 23, 42, 0.6) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
  color: #94a3b8 !important;
}

.filter-group :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%) !important;
  border-color: transparent !important;
  color: white !important;
  box-shadow: none !important;
}

/* Task Table */
.task-table-wrapper {
  padding: 0 28px 28px;
}

.task-table {
  width: 100%;
  background: transparent !important;
}

.task-table :deep(.el-table__header) {
  background: transparent !important;
}

.task-table :deep(.el-table__body) {
  background: transparent !important;
}

.task-table :deep(.el-table__row) {
  background: transparent !important;
  transition: background 0.3s ease;
}

.task-table :deep(.el-table__row:hover) {
  background: rgba(255, 255, 255, 0.03) !important;
}

.task-table :deep(.el-table__cell) {
  padding: 16px 0 !important;
}

/* Task ID */
.task-id {
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 0.8125rem;
  color: #64748b;
  background: rgba(15, 23, 42, 0.6);
  padding: 4px 10px;
  border-radius: 6px;
}

/* Task Title */
.task-title {
  display: flex;
  align-items: center;
}

.title-text {
  font-size: 0.9375rem;
  font-weight: 500;
  color: #e2e8f0;
}

/* Genre Tag */
.genre-tag {
  font-size: 0.8125rem;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 10px;
  border-radius: 6px;
  text-transform: capitalize;
}

/* Status Badge */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 0.8125rem;
  font-weight: 500;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-pending {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.status-pending .status-dot {
  background: #f59e0b;
  animation: pulse 2s ease-in-out infinite;
}

.status-running {
  background: rgba(6, 182, 212, 0.15);
  color: #06b6d4;
}

.status-running .status-dot {
  background: #06b6d4;
  animation: pulse 2s ease-in-out infinite;
}

.status-completed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.status-completed .status-dot {
  background: #10b981;
}

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.status-failed .status-dot {
  background: #ef4444;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

/* Progress */
.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress-text {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #e2e8f0;
  min-width: 36px;
  text-align: right;
}

/* Time Text */
.time-text {
  font-size: 0.8125rem;
  color: #64748b;
}

/* Action Buttons */
.action-buttons {
  display: flex;
  gap: 8px;
}

.action-btn {
  width: 32px;
  height: 32px;
  padding: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px !important;
}

.view-btn {
  background: rgba(6, 182, 212, 0.15) !important;
  border-color: rgba(6, 182, 212, 0.3) !important;
  color: #06b6d4 !important;
}

.view-btn:hover {
  background: rgba(6, 182, 212, 0.25) !important;
}

.cancel-btn {
  background: rgba(239, 68, 68, 0.15) !important;
  border-color: rgba(239, 68, 68, 0.3) !important;
  color: #ef4444 !important;
}

.cancel-btn:hover {
  background: rgba(239, 68, 68, 0.25) !important;
}

/* Loading */
.task-table :deep(.el-loading-mask) {
  background: rgba(15, 23, 42, 0.8) !important;
  backdrop-filter: blur(4px);
}

/* Responsive */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .card-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
  
  .task-table-wrapper {
    padding: 0 16px 16px;
    overflow-x: auto;
  }
}
</style>
