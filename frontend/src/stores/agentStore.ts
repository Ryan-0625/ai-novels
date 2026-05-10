/* Pinia Agent 状态管理 (Step 12/13) */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiV2, { type AgentInfo } from '@/services/api-v2'
import { wsService } from '@/services/websocket'

export const useAgentStore = defineStore('agent', () => {
  const agents = ref<AgentInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedAgent = ref<string | null>(null)
  const wsConnected = ref(false)

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

  function updateAgentFromWS(payload: any) {
    const idx = agents.value.findIndex(a => a.name === payload.name)
    if (idx >= 0) {
      agents.value[idx] = { ...agents.value[idx], ...payload }
    }
  }

  function connectWS() {
    wsService.connect({
      onOpen: () => { wsConnected.value = true },
      onClose: () => { wsConnected.value = false },
      onAgentStatus: updateAgentFromWS,
    })
  }

  function disconnectWS() {
    wsService.disconnect()
    wsConnected.value = false
  }

  return {
    agents, loading, error, selectedAgent, wsConnected,
    activeCount, idleCount,
    fetchAgents, getAgentMetrics,
    updateAgentFromWS, connectWS, disconnectWS,
  }
})
