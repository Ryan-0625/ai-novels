/* WebSocket 实时通信服务 (Step 12) */

interface WSMessage {
  type: 'task_update' | 'agent_status' | 'system_metric' | 'heartbeat'
  payload: any
  timestamp: number
}

interface WSCallbacks {
  onTaskUpdate?: (data: any) => void
  onAgentStatus?: (data: any) => void
  onSystemMetric?: (data: any) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
}

class WebSocketService {
  private ws: WebSocket | null = null
  private url: string
  private reconnectTimer: number | null = null
  private heartbeatTimer: number | null = null
  private callbacks: WSCallbacks = {}
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000

  constructor(url?: string) {
    this.url = url || this._inferUrl()
  }

  private _inferUrl(): string {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8004'
    const wsProto = apiUrl.startsWith('https') ? 'wss' : 'ws'
    const host = apiUrl.replace(/^https?:\/\//, '').replace(/\/api\/v\d+$/, '')
    return `${wsProto}://${host}/ws`
  }

  connect(callbacks: WSCallbacks = {}): void {
    this.callbacks = callbacks
    if (this.ws?.readyState === WebSocket.OPEN) return

    try {
      this.ws = new WebSocket(this.url)
      this._bindEvents()
    } catch (e) {
      console.error('WebSocket connection failed:', e)
      this._scheduleReconnect()
    }
  }

  private _bindEvents(): void {
    if (!this.ws) return

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this._startHeartbeat()
      this.callbacks.onOpen?.()
    }

    this.ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        this._handleMessage(msg)
      } catch (e) {
        console.warn('Invalid WS message:', event.data)
      }
    }

    this.ws.onclose = () => {
      this._stopHeartbeat()
      this.callbacks.onClose?.()
      this._scheduleReconnect()
    }

    this.ws.onerror = (error) => {
      this.callbacks.onError?.(error)
    }
  }

  private _handleMessage(msg: WSMessage): void {
    switch (msg.type) {
      case 'task_update':
        this.callbacks.onTaskUpdate?.(msg.payload)
        break
      case 'agent_status':
        this.callbacks.onAgentStatus?.(msg.payload)
        break
      case 'system_metric':
        this.callbacks.onSystemMetric?.(msg.payload)
        break
    }
  }

  private _startHeartbeat(): void {
    this.heartbeatTimer = window.setInterval(() => {
      this.send({ type: 'heartbeat', payload: {}, timestamp: Date.now() })
    }, 30000)
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      // WebSocket 端点不可用 — 前端应使用 SSE (connectSSE) 获取实时事件
      return
    }
    this.reconnectAttempts++
    this.reconnectTimer = window.setTimeout(() => {
      this.connect(this.callbacks)
    }, this.reconnectDelay * this.reconnectAttempts)
  }

  send(data: WSMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this._stopHeartbeat()
    this.ws?.close()
    this.ws = null
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsService = new WebSocketService()
export type { WSMessage, WSCallbacks }
