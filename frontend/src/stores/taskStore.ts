/* Pinia 任务状态管理 (Step 12/13) */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiV2, { type TaskItem } from '@/services/api-v2'
import { wsService } from '@/services/websocket'

export interface TaskFilter {
  status?: string
  agentName?: string
}

export const useTaskStore = defineStore('task', () => {
  // State
  const tasks = ref<TaskItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedTaskId = ref<string | null>(null)
  const wsConnected = ref(false)

  // Getters
  const taskCount = computed(() => tasks.value.length)
  const runningCount = computed(() => tasks.value.filter(t => t.status === 'running').length)
  const idleCount = computed(() => tasks.value.filter(t => t.status === 'idle').length)

  const filteredTasks = computed(() => {
    return (filter: TaskFilter) => {
      let result = tasks.value
      if (filter.status) result = result.filter(t => t.status === filter.status)
      if (filter.agentName) result = result.filter(t => t.agent_name === filter.agentName)
      return result
    }
  })

  const selectedTask = computed(() => {
    if (!selectedTaskId.value) return null
    return tasks.value.find(t => t.task_id === selectedTaskId.value) || null
  })

  // Actions
  async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
      const resp = await apiV2.listTasks()
      tasks.value = resp.tasks || []
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch tasks'
    } finally {
      loading.value = false
    }
  }

  async function getTaskDetail(taskId: string) {
    try {
      return await apiV2.getTask(taskId)
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  async function actionTask(taskId: string, action: 'pause' | 'resume' | 'cancel') {
    try {
      return await apiV2.taskAction(taskId, action)
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  function selectTask(taskId: string | null) {
    selectedTaskId.value = taskId
  }

  function updateTaskFromWS(payload: any) {
    const idx = tasks.value.findIndex(t => t.task_id === payload.task_id)
    if (idx >= 0) {
      tasks.value[idx] = { ...tasks.value[idx], ...payload }
    } else if (payload.task_id) {
      tasks.value.push(payload)
    }
  }

  function connectWS() {
    wsService.connect({
      onOpen: () => { wsConnected.value = true },
      onClose: () => { wsConnected.value = false },
      onTaskUpdate: updateTaskFromWS,
    })
  }

  function disconnectWS() {
    wsService.disconnect()
    wsConnected.value = false
  }

  return {
    tasks, loading, error, selectedTaskId, wsConnected,
    taskCount, runningCount, idleCount, filteredTasks, selectedTask,
    fetchTasks, getTaskDetail, actionTask, selectTask,
    updateTaskFromWS, connectWS, disconnectWS,
  }
})
