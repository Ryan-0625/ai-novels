<script setup lang="ts">
import { computed } from 'vue'
import { Timer, EditPen, TrendCharts, Clock, CircleCheck } from '@element-plus/icons-vue'

export interface GenerationStatsData {
  total_words: number
  target_words?: number
  chapters_completed: number
  total_chapters: number
  elapsed_seconds: number
  eta_seconds?: number
  speed_wpm?: number  // words per minute
}

const props = defineProps<{
  stats: GenerationStatsData
}>()

function formatTime(seconds: number): string {
  if (!seconds || seconds <= 0) return '--'
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

function formatWords(n: number): string {
  if (!n) return '0'
  if (n >= 10000) return `${(n / 10000).toFixed(1)}w`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return n.toString()
}

const progress = computed(() => {
  if (!props.stats.total_chapters) return 0
  return Math.round((props.stats.chapters_completed / props.stats.total_chapters) * 100)
})

const wordProgress = computed(() => {
  if (!props.stats.target_words) return 0
  return Math.min(100, Math.round((props.stats.total_words / props.stats.target_words) * 100))
})
</script>

<template>
  <div class="stats-container">
    <div class="stat-card">
      <div class="stat-icon words-icon">
        <el-icon :size="20"><EditPen /></el-icon>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ formatWords(stats.total_words) }}</div>
        <div class="stat-label">总字数</div>
        <div v-if="stats.target_words" class="stat-target">目标 {{ formatWords(stats.target_words) }}</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon time-icon">
        <el-icon :size="20"><Timer /></el-icon>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ formatTime(stats.elapsed_seconds) }}</div>
        <div class="stat-label">已用时间</div>
        <div v-if="stats.eta_seconds" class="stat-target">预计剩余 {{ formatTime(stats.eta_seconds) }}</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon chapter-icon">
        <el-icon :size="20"><CircleCheck /></el-icon>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ stats.chapters_completed }} / {{ stats.total_chapters }}</div>
        <div class="stat-label">已完成章节</div>
        <div class="stat-bar">
          <div class="stat-bar-fill" :style="{ width: `${progress}%` }"></div>
        </div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon speed-icon">
        <el-icon :size="20"><TrendCharts /></el-icon>
      </div>
      <div class="stat-body">
        <div class="stat-value">{{ stats.speed_wpm ?? '--' }}</div>
        <div class="stat-label">生成速度 (字/分)</div>
        <div v-if="stats.target_words" class="stat-target">
          <span class="word-progress-text">{{ wordProgress }}% 字数目标</span>
          <div class="stat-bar">
            <div class="stat-bar-fill accent" :style="{ width: `${wordProgress}%` }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.stats-container {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  background: var(--bg-glass);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-glass);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  display: flex;
  gap: 16px;
  align-items: flex-start;
  transition: all var(--transition-normal);
}

.stat-card:hover {
  border-color: var(--border-glow);
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.words-icon {
  background: rgba(16, 185, 129, 0.15);
  color: var(--accent-emerald);
}

.time-icon {
  background: rgba(6, 182, 212, 0.15);
  color: var(--accent-cyan);
}

.chapter-icon {
  background: rgba(139, 92, 246, 0.15);
  color: var(--accent-purple);
}

.speed-icon {
  background: rgba(245, 158, 11, 0.15);
  color: var(--accent-amber);
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.5px;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-top: 4px;
}

.stat-target {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 6px;
}

.stat-bar {
  height: 3px;
  background: var(--bg-glass-light);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-top: 6px;
}

.stat-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-purple), var(--accent-cyan));
  border-radius: var(--radius-full);
  transition: width var(--transition-slow);
}

.stat-bar-fill.accent {
  background: linear-gradient(90deg, var(--accent-amber), var(--accent-pink));
}

.word-progress-text {
  display: block;
  margin-bottom: 4px;
}
</style>
