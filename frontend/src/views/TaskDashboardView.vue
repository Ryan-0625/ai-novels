<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useAgentStore } from '@/stores/agentStore'
import { connectSSE, type SSEEvent } from '@/services/api-v2'
import DagVisualizer from '@/components/DagVisualizer.vue'
import type { DagNode, DagEdge } from '@/components/DagVisualizer.vue'

const taskStore = useTaskStore()
const agentStore = useAgentStore()

// SSE 连接状态
const sseConnected = ref(false)
let disconnectSSE: (() => void) | null = null

// Agent → DAG 节点标签映射
const workflowStages = [
  { id: 'config_enhancer', label: '配置增强' },
  { id: 'outline_planner', label: '大纲规划' },
  { id: 'character_generator', label: '角色生成' },
  { id: 'world_builder', label: '世界构建' },
  { id: 'content_generator', label: '内容生成' },
  { id: 'quality_checker', label: '质量检查' },
]

// DAG 边（固定拓扑）
const dagEdges: DagEdge[] = [
  { source: 'config_enhancer', target: 'outline_planner' },
  { source: 'outline_planner', target: 'character_generator' },
  { source: 'outline_planner', target: 'world_builder' },
  { source: 'character_generator', target: 'content_generator' },
  { source: 'world_builder', target: 'content_generator' },
  { source: 'content_generator', target: 'quality_checker' },
]

// 从实际任务状态构建 DAG 节点
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

// 当前激活的节点（用于高亮）
const activeNodeId = computed(() => {
  const running = dagNodes.value.find((n) => n.status === 'running')
  return running?.id || null
})

// SSE 事件处理 → 实时更新 DAG
function handleSSEEvent(event: SSEEvent) {
  const payload = event.payload || {}
  const agentName = payload.agent_name || event.source

  if (!agentName) return

  // 当收到 agent 状态事件，刷新 store
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

// 点击 DAG 节点 → 过滤任务列表
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
  taskStore.connectWS()
  agentStore.connectWS()

  // SSE 连接（作为 WebSocket 的补充）
  disconnectSSE = connectSSE(
    handleSSEEvent,
    () => { sseConnected.value = false },
    () => { sseConnected.value = true },
  )

  // 轮询保底
  refreshInterval = window.setInterval(() => {
    taskStore.fetchTasks()
    agentStore.fetchAgents()
  }, 8000)
})

onUnmounted(() => {
  taskStore.disconnectWS()
  agentStore.disconnectWS()
  if (disconnectSSE) disconnectSSE()
  if (refreshInterval) clearInterval(refreshInterval)
})

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    idle: 'info',
    pending: 'warning',
  }
  return map[status] || 'info'
}
</script>

<template>
  <div class="task-dashboard p-4">
    <h2 class="text-2xl font-bold text-white mb-4">任务调度监控中心</h2>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <el-card class="stat-card" shadow="hover">
        <div class="text-3xl font-bold text-cyan-400">{{ taskStore.taskCount }}</div>
        <div class="text-sm text-slate-400">总任务数</div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="text-3xl font-bold text-emerald-400">{{ taskStore.runningCount }}</div>
        <div class="text-sm text-slate-400">运行中</div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="text-3xl font-bold text-blue-400">{{ agentStore.idleCount }}</div>
        <div class="text-sm text-slate-400">空闲 Agent</div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="text-3xl font-bold text-amber-400">{{ agentStore.activeCount }}</div>
        <div class="text-sm text-slate-400">忙碌 Agent</div>
      </el-card>
    </div>

    <!-- DAG 可视化 -->
    <el-card class="mb-6" shadow="never">
      <template #header>
        <span class="font-bold text-white">工作流 DAG</span>
        <el-tag v-if="sseConnected" type="success" size="small" class="ml-2">SSE 实时</el-tag>
        <el-tag v-else-if="taskStore.wsConnected" type="warning" size="small" class="ml-2">WebSocket</el-tag>
        <el-tag v-else type="info" size="small" class="ml-2">轮询模式</el-tag>
      </template>
      <DagVisualizer
        :nodes="dagNodes"
        :edges="dagEdges"
        :width="900"
        :height="300"
        :active-node-id="activeNodeId"
        @node-click="onNodeClick"
      />
      <div class="mt-2 text-xs text-slate-500">
         <span v-if="filterAgent" class="text-cyan-400">过滤: {{ workflowStages.find(s => s.id === filterAgent)?.label }} <el-link type="info" @click="filterAgent = null">清除</el-link></span>
         <span v-else>点击节点查看对应 Agent 任务</span>
      </div>
    </el-card>

    <!-- 任务列表 -->
    <el-card shadow="never">
      <template #header>
        <span class="font-bold text-white">活跃任务</span>
        <span v-if="filterAgent" class="text-sm text-cyan-400 ml-2">(已过滤)</span>
      </template>
      <el-table :data="filteredTasks" v-loading="taskStore.loading">
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
    </el-card>
  </div>
</template>

<style scoped>
.task-dashboard {
  background: #0b1120;
  min-height: 100vh;
}
.stat-card {
  background: #1e293b;
  border: none;
}
</style>
