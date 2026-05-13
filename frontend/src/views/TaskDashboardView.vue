<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useAgentStore } from '@/stores/agentStore'
import { connectSSE, type SSEEvent } from '@/services/api-v2'
import DagVisualizer from '@/components/DagVisualizer.vue'
import type { DagNode, DagEdge } from '@/components/DagVisualizer.vue'
import { DataLine, Connection, CircleCheck, Warning } from '@element-plus/icons-vue'

const taskStore = useTaskStore()
const agentStore = useAgentStore()

const sseConnected = ref(false)
let disconnectSSE: (() => void) | null = null

const workflowStages = [
  { id: 'config_enhancer', label: '配置增强' },
  { id: 'outline_planner', label: '大纲规划' },
  { id: 'character_generator', label: '角色生成' },
  { id: 'world_builder', label: '世界构建' },
  { id: 'content_generator', label: '内容生成' },
  { id: 'quality_checker', label: '质量检查' },
]

const dagEdges: DagEdge[] = [
  { source: 'config_enhancer', target: 'outline_planner' },
  { source: 'outline_planner', target: 'character_generator' },
  { source: 'outline_planner', target: 'world_builder' },
  { source: 'character_generator', target: 'content_generator' },
  { source: 'world_builder', target: 'content_generator' },
  { source: 'content_generator', target: 'quality_checker' },
]

const dagNodes = computed<DagNode[]>(() => {
  const taskMap = new Map<string, string>()
  for (const t of taskStore.tasks) {
    if (t.agent_name && !taskMap.has(t.agent_name)) {
      taskMap.set(t.agent_name, t.status)
    }
  }
  return workflowStages.map((stage) => {
    let status: DagNode['status'] = 'pending'
    const agent = agentStore.agents.find((a) => a.name === stage.id)
    if (agent) {
      if (agent.status === 'busy') status = 'running'
      else if (agent.status === 'idle') status = 'completed'
    }
    const taskStatus = taskMap.get(stage.id)
    if (taskStatus === 'running') status = 'running'
    else if (taskStatus === 'completed') status = 'completed'
    else if (taskStatus === 'failed') status = 'failed'
    return { id: stage.id, label: stage.label, status }
  })
})

const activeNodeId = computed(() => {
  const running = dagNodes.value.find((n) => n.status === 'running')
  return running?.id || null
})

function handleSSEEvent(event: SSEEvent) {
  const payload = event.payload || {}
  const agentName = payload.agent_name || event.source
  if (!agentName) return
  if (
    event.type === 'agent.started' ||
    event.type === 'agent.completed' ||
    event.type === 'agent.failed' ||
    event.type === 'task.started' ||
    event.type === 'task.completed' ||
    event.type === 'task.failed'
  ) {
    taskStore.fetchTasks()
    agentStore.fetchAgents()
  }
}

const filterAgent = ref<string | null>(null)
const filteredTasks = computed(() => {
  if (!filterAgent.value) return taskStore.tasks
  return taskStore.tasks.filter((t) => t.agent_name === filterAgent.value)
})

function onNodeClick(nodeId: string) {
  filterAgent.value = filterAgent.value === nodeId ? null : nodeId
}

let refreshInterval: number | undefined

onMounted(() => {
  taskStore.fetchTasks()
  agentStore.fetchAgents()
  taskStore.connectSSEStream()
  agentStore.connectSSEStream()
  disconnectSSE = connectSSE(
    handleSSEEvent,
    () => { sseConnected.value = false },
    () => { sseConnected.value = true },
  )
  refreshInterval = window.setInterval(() => {
    taskStore.fetchTasks()
    agentStore.fetchAgents()
  }, 8000)
})

onUnmounted(() => {
  taskStore.disconnectSSEStream()
  agentStore.disconnectSSEStream()
  if (disconnectSSE) disconnectSSE()
  if (refreshInterval) clearInterval(refreshInterval)
})

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    running: 'primary', completed: 'success', failed: 'danger',
    idle: 'info', pending: 'warning',
  }
  return map[status] || 'info'
}
</script>

<template>
  <div class="task-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-icon">
        <el-icon :size="24"><DataLine /></el-icon>
      </div>
      <div>
        <h1 class="page-title">任务调度监控中心</h1>
        <p class="page-desc">DAG 工作流可视化与实时状态监控</p>
      </div>
      <div class="header-tags">
        <el-tag v-if="sseConnected" type="success" size="small" effect="dark">
          <el-icon class="mr-1" :size="14"><Connection /></el-icon>SSE 实时
        </el-tag>
        <el-tag v-else type="info" size="small" effect="dark">轮询模式</el-tag>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="glass-card stat-card">
        <div class="stat-value cyan">{{ taskStore.taskCount }}</div>
        <div class="stat-label">总任务数</div>
      </div>
      <div class="glass-card stat-card">
        <div class="stat-value green">{{ taskStore.runningCount }}</div>
        <div class="stat-label">运行中</div>
      </div>
      <div class="glass-card stat-card">
        <div class="stat-value blue">{{ agentStore.idleCount }}</div>
        <div class="stat-label">空闲 Agent</div>
      </div>
      <div class="glass-card stat-card">
        <div class="stat-value amber">{{ agentStore.activeCount }}</div>
        <div class="stat-label">忙碌 Agent</div>
      </div>
    </div>

    <!-- DAG 可视化 -->
    <div class="glass-card dag-section">
      <div class="card-header">
        <span class="card-title">工作流 DAG</span>
        <span v-if="filterAgent" class="filter-hint">
          已过滤: {{ workflowStages.find(s => s.id === filterAgent)?.label }}
          <el-link type="info" :underline="false" @click="filterAgent = null">清除</el-link>
        </span>
      </div>
      <DagVisualizer
        :nodes="dagNodes"
        :edges="dagEdges"
        :width="900"
        :height="300"
        :active-node-id="activeNodeId"
        @node-click="onNodeClick"
      />
      <div class="dag-hint">
        <span v-if="!filterAgent">点击节点查看对应 Agent 任务</span>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="glass-card table-section">
      <div class="card-header">
        <span class="card-title">活跃任务</span>
        <span v-if="filterAgent" class="filter-hint">(已过滤)</span>
      </div>
      <el-table :data="filteredTasks" v-loading="taskStore.loading" class="glass-table">
        <el-table-column prop="task_id" label="任务ID" width="180" />
        <el-table-column prop="agent_name" label="Agent" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusBadge(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column prop="created_at" label="创建时间" />
      </el-table>
    </div>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.task-dashboard {
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
  background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3);
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

.header-tags {
  margin-left: auto;
}

.mr-1 {
  margin-right: 4px;
}

/* 统计卡片网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  padding: 24px;
  text-align: center;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: rgba(56, 189, 248, 0.3);
}

.stat-value {
  font-size: 2.5rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 8px;
  letter-spacing: -1px;
}

.stat-value.cyan { color: #22d3ee; }
.stat-value.green { color: #34d399; }
.stat-value.blue { color: #60a5fa; }
.stat-value.amber { color: #fbbf24; }

.stat-label {
  font-size: 0.875rem;
  color: #94a3b8;
}

/* DAG 区域 */
.dag-section {
  padding: 24px;
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title {
  font-weight: 600;
  color: #f8fafc;
  font-size: 1rem;
}

.filter-hint {
  font-size: 0.8125rem;
  color: #22d3ee;
}

.dag-hint {
  margin-top: 12px;
  font-size: 0.8125rem;
  color: #64748b;
}

/* 任务列表 */
.table-section {
  padding: 24px;
}

.glass-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.02);
  --el-table-border-color: rgba(255, 255, 255, 0.05);
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #94a3b8;
  --el-table-row-hover-bg-color: rgba(255, 255, 255, 0.03);
}
</style>
