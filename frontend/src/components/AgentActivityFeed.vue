<template>
  <div class="agent-activity-feed">
    <div class="feed-header">
      <el-icon :size="18"><Timer /></el-icon>
      <span class="feed-title">Agent 活动流</span>
      <el-badge :value="activities.length" class="feed-badge" />
    </div>

    <div class="feed-timeline" ref="timelineRef">
      <div
        v-for="(item, index) in sortedActivities"
        :key="item.id"
        class="timeline-item"
        :class="[`status-${item.status}`]"
        @click="toggleExpand(item.id)"
      >
        <div class="timeline-marker">
          <div class="marker-dot" :class="item.status"></div>
          <div v-if="index < sortedActivities.length - 1" class="marker-line"></div>
        </div>

        <div class="timeline-content">
          <div class="timeline-main">
            <span class="agent-name">{{ formatAgentName(item.agentName) }}</span>
            <span class="activity-stage">{{ item.stage }}</span>
            <span class="activity-status" :class="item.status">{{ statusLabel(item.status) }}</span>
          </div>
          <div class="timeline-meta">
            <span class="meta-time">{{ formatTime(item.timestamp) }}</span>
            <span v-if="item.duration" class="meta-duration">{{ item.duration }}ms</span>
          </div>

          <div v-if="expanded === item.id && item.details" class="timeline-details">
            <div v-if="item.details.input" class="detail-block">
              <div class="detail-label">输入</div>
              <pre class="detail-code">{{ truncate(item.details.input, 300) }}</pre>
            </div>
            <div v-if="item.details.output" class="detail-block">
              <div class="detail-label">输出</div>
              <pre class="detail-code">{{ truncate(item.details.output, 300) }}</pre>
            </div>
            <div v-if="item.details.error" class="detail-block">
              <div class="detail-label">错误</div>
              <pre class="detail-code error">{{ item.details.error }}</pre>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activities.length === 0" class="feed-empty">
        <el-icon :size="24"><InfoFilled /></el-icon>
        <span>暂无活动记录</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Timer, InfoFilled } from '@element-plus/icons-vue'

export interface ActivityItem {
  id: string
  agentName: string
  stage: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  timestamp: number
  duration?: number
  details?: {
    input?: string
    output?: string
    error?: string
  }
}

const props = defineProps<{
  activities: ActivityItem[]
}>()

const expanded = ref<string | null>(null)

const sortedActivities = computed(() => {
  return [...props.activities].sort((a, b) => b.timestamp - a.timestamp)
})

function toggleExpand(id: string) {
  expanded.value = expanded.value === id ? null : id
}

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

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    running: '执行中',
    completed: '完成',
    failed: '失败',
  }
  return map[status] || status
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max) + '\n... (已截断)'
}
</script>

<style scoped>
.agent-activity-feed {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 600px;
}

.feed-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.feed-title {
  font-size: 1rem;
  font-weight: 600;
  color: #f8fafc;
  flex: 1;
}

.feed-badge :deep(.el-badge__content) {
  background: #8b5cf6;
  border: none;
}

.feed-timeline {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  cursor: pointer;
  transition: background 0.2s;
  border-radius: 8px;
}

.timeline-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
  flex-shrink: 0;
}

.marker-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid transparent;
}

.marker-dot.pending { background: #f59e0b; }
.marker-dot.running { background: #06b6d4; box-shadow: 0 0 8px rgba(6, 182, 212, 0.5); }
.marker-dot.completed { background: #10b981; }
.marker-dot.failed { background: #ef4444; }

.marker-line {
  flex: 1;
  width: 2px;
  background: rgba(255, 255, 255, 0.08);
  margin-top: 4px;
  min-height: 20px;
}

.timeline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.timeline-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: #e2e8f0;
}

.activity-stage {
  font-size: 0.8125rem;
  color: #94a3b8;
}

.activity-status {
  font-size: 0.6875rem;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
}

.activity-status.pending { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.activity-status.running { background: rgba(6, 182, 212, 0.15); color: #06b6d4; }
.activity-status.completed { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.activity-status.failed { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

.timeline-meta {
  display: flex;
  gap: 12px;
  font-size: 0.75rem;
  color: #64748b;
}

.timeline-details {
  margin-top: 8px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 0.6875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
}

.detail-code {
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 0.75rem;
  color: #e2e8f0;
  background: rgba(0, 0, 0, 0.3);
  padding: 8px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
  margin: 0;
}

.detail-code.error {
  color: #ef4444;
}

.feed-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: #64748b;
  font-size: 0.875rem;
}
</style>
