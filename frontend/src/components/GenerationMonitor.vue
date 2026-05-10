<template>
  <div class="generation-monitor">
    <div class="monitor-header">
      <el-icon :size="18"><VideoPlay /></el-icon>
      <span class="monitor-title">实时生成监控</span>
      <span class="monitor-status" :class="{ active: isConnected }">
        <span class="status-dot"></span>
        {{ isConnected ? '已连接' : '未连接' }}
      </span>
    </div>

    <div v-if="currentActivity" class="current-activity">
      <div class="activity-agent">
        <el-avatar :size="32" :class="`agent-avatar agent-${currentActivity.agentName}`">
          {{ currentActivity.agentName.charAt(0).toUpperCase() }}
        </el-avatar>
        <div class="activity-info">
          <div class="activity-name">{{ formatAgentName(currentActivity.agentName) }}</div>
          <div class="activity-stage">{{ currentActivity.stage }}</div>
        </div>
      </div>
      <el-progress
        :percentage="Math.round(currentActivity.progress * 100)"
        :status="currentActivity.progress >= 1 ? 'success' : ''"
        :stroke-width="6"
        class="activity-progress"
      />
    </div>

    <div v-else class="no-activity">
      <el-icon :size="32"><Loading /></el-icon>
      <span>等待任务启动...</span>
    </div>

    <div v-if="llmCall" class="llm-call">
      <el-icon :size="14"><Cpu /></el-icon>
      <span class="llm-text">{{ llmCall.provider }}/{{ llmCall.model }}</span>
      <span class="llm-badge" :class="llmCall.status">{{ llmStatusText }}</span>
    </div>

    <div v-if="recentOutput" class="output-preview">
      <div class="output-label">最新输出</div>
      <div class="output-text">{{ recentOutput }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { VideoPlay, Loading, Cpu } from '@element-plus/icons-vue'

interface Activity {
  agentName: string
  stage: string
  progress: number
  timestamp: number
}

const props = defineProps<{
  isConnected: boolean
  currentActivity?: Activity | null
  llmCall?: { provider: string; model: string; status: 'requesting' | 'streaming' | 'done' | 'error' } | null
  recentOutput?: string
}>()

const llmStatusText = computed(() => {
  switch (props.llmCall?.status) {
    case 'requesting': return '请求中'
    case 'streaming': return '流式输出'
    case 'done': return '完成'
    case 'error': return '错误'
    default: return ''
  }
})

function formatAgentName(name: string): string {
  const map: Record<string, string> = {
    content_generator: '内容生成',
    outline_planner: '大纲规划',
    character_generator: '角色生成',
    world_builder: '世界构建',
    quality_checker: '质量检查',
    config_enhancer: '配置增强',
    health_checker: '健康检查',
    chapter_summary: '章节摘要',
    hook_generator: '钩子生成',
    conflict_generator: '冲突设计',
    coordinator: '协调器',
  }
  return map[name] || name
}
</script>

<style scoped>
.generation-monitor {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.monitor-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.monitor-title {
  font-size: 1rem;
  font-weight: 600;
  color: #f8fafc;
  flex: 1;
}

.monitor-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: #64748b;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
}

.monitor-status.active {
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #64748b;
}

.monitor-status.active .status-dot {
  background: #10b981;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.current-activity {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-agent {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-avatar {
  font-size: 0.875rem;
  font-weight: 700;
  background: linear-gradient(135deg, #8b5cf6, #ec4899) !important;
  color: white;
}

.activity-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.activity-name {
  font-size: 0.9375rem;
  font-weight: 600;
  color: #e2e8f0;
}

.activity-stage {
  font-size: 0.8125rem;
  color: #94a3b8;
}

.activity-progress :deep(.el-progress-bar__outer) {
  background: rgba(255, 255, 255, 0.1);
}

.no-activity {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  color: #64748b;
  font-size: 0.875rem;
}

.llm-call {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  font-size: 0.8125rem;
  color: #94a3b8;
  width: fit-content;
}

.llm-text {
  color: #e2e8f0;
}

.llm-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.6875rem;
  font-weight: 500;
}

.llm-badge.requesting {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.llm-badge.streaming {
  background: rgba(6, 182, 212, 0.2);
  color: #06b6d4;
}

.llm-badge.done {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.llm-badge.error {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.output-preview {
  background: rgba(15, 23, 42, 0.4);
  border-radius: 10px;
  padding: 12px;
}

.output-label {
  font-size: 0.6875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.output-text {
  font-size: 0.8125rem;
  color: #e2e8f0;
  line-height: 1.5;
  max-height: 80px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
