<script setup lang="ts">
export interface TimelineStage {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  elapsed_seconds?: number
  progress?: number  // 0-100 for sub-stages within a stage
}

const props = defineProps<{
  stages: TimelineStage[]
  currentStageId?: string | null
}>()
</script>

<template>
  <div class="timeline">
    <div
      v-for="(stage, index) in stages"
      :key="stage.id"
      class="timeline-stage"
      :class="[
        `status-${stage.status}`,
        { active: stage.id === currentStageId }
      ]"
    >
      <div class="stage-connector">
        <div class="stage-dot">
          <div v-if="stage.status === 'running'" class="dot-pulse"></div>
          <el-icon v-else-if="stage.status === 'completed'" :size="14" color="#10b981"><Check /></el-icon>
          <el-icon v-else-if="stage.status === 'failed'" :size="14" color="#ef4444"><Close /></el-icon>
        </div>
        <div v-if="index < stages.length - 1" class="stage-line" :class="{ filled: stage.status === 'completed' }"></div>
      </div>
      <div class="stage-content">
        <div class="stage-label">{{ stage.label }}</div>
        <div class="stage-meta">
          <span v-if="stage.elapsed_seconds !== undefined" class="stage-time">
            {{ formatTime(stage.elapsed_seconds) }}
          </span>
          <span v-else-if="stage.status === 'pending'" class="stage-pending">等待中</span>
          <span v-else-if="stage.status === 'running'" class="stage-running">进行中</span>
        </div>
        <!-- 内部进度条（子阶段，如章节生成进度） -->
        <div v-if="stage.progress !== undefined && stage.status === 'running'" class="stage-progress-bar">
          <div class="stage-progress-fill" :style="{ width: `${stage.progress}%` }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
function formatTime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60)
    const s = Math.round(seconds % 60)
    return `${m}m ${s}s`
  }
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}
</script>

<style scoped>
@import '@/styles/glassmorphism.css';

.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-stage {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  transition: all var(--transition-normal);
}

.timeline-stage.active {
  background: rgba(6, 182, 212, 0.05);
  border-radius: var(--radius-sm);
  padding-left: 8px;
  padding-right: 8px;
}

.stage-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 24px;
}

.stage-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border: 2px solid var(--border-glass);
  flex-shrink: 0;
  transition: all var(--transition-normal);
}

.status-completed .stage-dot {
  background: rgba(16, 185, 129, 0.2);
  border-color: var(--accent-emerald);
}

.status-running .stage-dot {
  background: rgba(6, 182, 212, 0.2);
  border-color: var(--accent-cyan);
}

.status-failed .stage-dot {
  background: rgba(239, 68, 68, 0.2);
  border-color: #ef4444;
}

.dot-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-cyan);
  animation: dot-pulse 1.5s infinite;
}

@keyframes dot-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.5; }
}

.stage-line {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: var(--border-glass);
  margin: 4px 0;
  transition: background var(--transition-normal);
}

.stage-line.filled {
  background: var(--accent-emerald);
}

.stage-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
}

.stage-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.stage-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.stage-time {
  color: var(--accent-cyan);
  font-variant-numeric: tabular-nums;
}

.stage-pending {
  font-style: italic;
}

.stage-running {
  color: var(--accent-cyan);
  animation: blink 1.5s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.stage-progress-bar {
  height: 4px;
  background: var(--bg-glass-light);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-top: 4px;
}

.stage-progress-fill {
  height: 100%;
  background: var(--gradient-aurora);
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}
</style>
