/* Pinia Agent 状态管理 (Step 12/13) */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiV2, { connectSSE, type SSEEvent, type AgentInfo } from '@/services/api-v2'

export const useAgentStore = defineStore('agent', () => {
  const agents = ref<AgentInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedAgent = ref<string | null>(null)
  const sseConnected = ref(false)
  let _disconnectSSE: (() => void) | null = null

  const activeCount = computed(() => agents.value.filter(a => a.status === 'busy').length)
  const idleCount = computed(() => agents.value.filter(a => a.status === 'idle').length)

  async function fetchAgents() {
    loading.value = true
    error.value = null
    try {
      agents.value = await apiV2.listAgents()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch agents'
    } finally {
      loading.value = false
    }
  }

  async function getAgentMetrics(name: string) {
    try {
      return await apiV2.getAgentMetrics(name)
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  /** 连接SSE以接收实时agent状态更新 */
  function connectSSEStream() {
    if (_disconnectSSE) return
    _disconnectSSE = connectSSE(
      (event: SSEEvent) => {
        if (['agent.started', 'agent.completed', 'agent.failed', 'agent.message'].includes(event.type)) {
          fetchAgents()
        }
      },
      () => { sseConnected.value = false },
      () => { sseConnected.value = true },
      () => { sseConnected.value = false },
    )
  }

  function disconnectSSEStream() {
    if (_disconnectSSE) {
      _disconnectSSE()
      _disconnectSSE = null
    }
    sseConnected.value = false
  }

  return {
    agents, loading, error, selectedAgent, sseConnected,
    activeCount, idleCount,
    fetchAgents, getAgentMetrics,
    connectSSEStream, disconnectSSEStream,
  }
})
