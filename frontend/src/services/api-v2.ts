/* API v2 服务 — Step 11 ConfigHub + TaskOrchestrator (Step 12/13) */
import axios, { AxiosInstance } from 'axios'

const v2Config = {
  baseURL: import.meta.env.VITE_API_V2_URL || 'http://localhost:8004/api/v2',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
}

const v2: AxiosInstance = axios.create(v2Config)

v2.interceptors.request.use((config) => {
  config.headers = config.headers || {}
  config.headers['X-Request-ID'] = crypto.randomUUID()
  return config
})

v2.interceptors.response.use((response) => response.data)

export interface AgentInfo {
  name: string
  description: string
  status: string
  version: string
  capabilities: string[]
}

export interface TaskItem {
  task_id: string
  agent_name: string
  status: string
  priority: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface TaskListResponse {
  tasks: TaskItem[]
  total: number
}

export interface NovelPreset {
  name: string
  title: string
  genre: string
  description: string
}

export interface ConfigReloadResponse {
  success: boolean
  message: string
  timestamp: string
}

export interface SSEEvent {
  type: string
  source: string
  timestamp?: number
  payload: Record<string, any>
}

export type SSEHandler = (event: SSEEvent) => void

export function connectSSE(
  onEvent: SSEHandler,
  onError?: (err: Event) => void,
  onOpen?: () => void,
): () => void {
  const url = `${v2Config.baseURL}/events`
  const source = new EventSource(url)

  source.onopen = () => onOpen?.()
  source.onerror = (err) => onError?.(err)
  source.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data)
      onEvent(data as SSEEvent)
    } catch {
      // ignore malformed events
    }
  }

  return () => source.close()
}

export const apiV2 = {
  // --- 任务管理 ---
  createTask: (req: { agent_name: string; payload: Record<string, any>; priority?: string; timeout?: number }) =>
    v2.post('/tasks', req) as Promise<{ task_id: string; agent_name: string; status: string; message: string }>,
  listTasks: () => v2.get('/tasks') as Promise<TaskListResponse>,
  getTask: (taskId: string) => v2.get(`/tasks/${taskId}`) as Promise<any>,
  taskAction: (taskId: string, action: 'pause' | 'resume' | 'cancel') =>
    v2.post(`/tasks/${taskId}/action`, { action }) as Promise<any>,
  listWorkflows: () => v2.get('/tasks/workflows/definitions') as Promise<any[]>,

  // --- Agent 管理 ---
  listAgents: () => v2.get('/agents') as Promise<AgentInfo[]>,
  getAgent: (name: string) => v2.get(`/agents/${name}`) as Promise<AgentInfo>,
  getAgentMetrics: (name: string) => v2.get(`/agents/${name}/metrics`) as Promise<any>,
  updateAgentConfig: (name: string, config: Record<string, any>) =>
    v2.patch(`/agents/${name}/config`, { config }) as Promise<any>,

  // --- 配置管理 ---
  getFullConfig: () => v2.get('/config') as Promise<Record<string, any>>,
  getConfigItem: (keyPath: string) => v2.get(`/config/${keyPath}`) as Promise<{ key: string; value: any }>,
  reloadConfig: () => v2.post('/config/reload') as Promise<ConfigReloadResponse>,
  listNovelPresets: () => v2.get('/config/novel/presets') as Promise<NovelPreset[]>,
  getNovelPreset: (name: string) => v2.get(`/config/novel/presets/${name}`) as Promise<any>,
}

export default apiV2
