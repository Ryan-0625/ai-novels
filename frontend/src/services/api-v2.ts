/* API v2 服务 — Step 11 ConfigHub + TaskOrchestrator (Step 12/13) */
import axios, { AxiosInstance } from 'axios'

const v2Config = {
  baseURL: import.meta.env.VITE_API_V2_URL || '/api/v2',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
}

const v2: AxiosInstance = axios.create(v2Config)

v2.interceptors.request.use((config) => {
  config.headers = config.headers || {}
  config.headers['X-Request-ID'] = crypto.randomUUID()
  // [Phase 1] 自动附加 JWT Token
  const token = localStorage.getItem('ai_novels_jwt')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
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

export interface SSEConnection {
  disconnect: () => void
  isConnected: () => boolean
}

/**
 * 创建 SSE 连接（支持自动重连）
 */
export function connectSSE(
  onEvent: SSEHandler,
  onError?: (err: Event) => void,
  onOpen?: () => void,
  onClose?: () => void,
): () => void {
  const url = `${v2Config.baseURL}/events`
  let source: EventSource | null = null
  let connected = false
  let reconnectTimer: number | null = null
  let disconnectRequested = false

  function connect() {
    if (disconnectRequested) return
    source = new EventSource(url)

    source.onopen = () => {
      connected = true
      onOpen?.()
    }

    source.onerror = (err) => {
      connected = false
      onError?.(err)
      onClose?.()
      // EventSource 内置自动重连, 无需手动创建新连接
      // 只记录错误, 由浏览器原生重连机制处理
    }

    source.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        onEvent(data as SSEEvent)
      } catch {
        // ignore malformed events
      }
    }
  }

  connect()

  return () => {
    disconnectRequested = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    source?.close()
    source = null
    connected = false
  }
}

/**
 * 创建可查询连接状态的 SSE 连接
 */
export function createSSEConnection(
  onEvent: SSEHandler,
  onError?: (err: Event) => void,
  onOpen?: () => void,
  onClose?: () => void,
): SSEConnection {
  const disconnect = connectSSE(onEvent, onError, onOpen, onClose)
  let _connected = false

  // 包装以暴露 isConnected
  const origOnOpen = onOpen
  const origOnError = onError
  const origOnClose = onClose

  const wrappedOnOpen = () => {
    _connected = true
    origOnOpen?.()
  }
  const wrappedOnError = (err: Event) => {
    _connected = false
    origOnError?.(err)
    origOnClose?.()
  }

  return {
    disconnect,
    isConnected: () => _connected,
  }
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

  // --- 章节管理（从 v1 迁移） ---
  getChapters: (taskId: string) => v2.get(`/tasks/${taskId}/chapters`) as Promise<any>,
  getChapterContent: (taskId: string, chapterNum: number) =>
    v2.get(`/tasks/${taskId}/chapters/${chapterNum}`) as Promise<any>,

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
  listNovelGenres: () => v2.get('/config/novel/genres') as Promise<{ value: string; label: string }[]>,
  listNovelStyles: () => v2.get('/config/novel/styles') as Promise<{ value: string; label: string; desc: string }[]>,

  // --- 系统/健康检查（从 v1 迁移） ---
  getSystemHealth: (deepCheck: boolean = false) =>
    v2.get('/health', { params: { deep_check: deepCheck } }) as Promise<any>,
  getSystemHealthFull: (deepCheck: boolean = false) =>
    v2.get('/system-health', { params: { deep_check: deepCheck } }) as Promise<any>,
  getComponentHealth: (componentName: string) =>
    v2.get(`/health/component/${componentName}`) as Promise<any>,
  immediateHealthCheck: () => v2.get('/health/check') as Promise<any>,

  // --- 生成进度 ---
  getGenerationProgress: (taskId: string) =>
    v2.get(`/tasks/${taskId}/generation/progress`) as Promise<any>,

  // --- 日志浏览 ---
  listLogCategories: () => v2.get('/logs') as Promise<any>,
  getLogLines: (category: string, params?: Record<string, any>) =>
    v2.get(`/logs/${category}`, { params }) as Promise<any>,
  getLogStats: (category: string) =>
    v2.get(`/logs/${category}/stats`) as Promise<any>,
  searchLogs: (params: { q: string; level?: string; max_results?: number }) =>
    v2.get('/logs/search', { params }) as Promise<any>,

  // --- [Phase 1] 认证 ---
  login: (username: string, password: string, tenant_id: string = 'default') =>
    v2.post('/auth/login', { username, password, tenant_id }) as Promise<any>,
  register: (username: string, email: string, password: string, tenant_id: string = 'default') =>
    v2.post('/auth/register', { username, email, password, tenant_id }) as Promise<any>,
  getMe: () => v2.get('/auth/me') as Promise<any>,
}

export default apiV2
