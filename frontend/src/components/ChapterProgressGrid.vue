<script setup lang="ts">
import { computed } from 'vue'

export interface ChapterInfo {
  chapter_num: number
  title?: string
  word_count?: number
  status: 'pending' | 'generating' | 'completed' | 'failed'
}

const props = withDefaults(defineProps<{
  chapters?: ChapterInfo[]
  totalChapters?: number
  columns?: number
}>(), {
  chapters: () => [],
  totalChapters: 20,
  columns: 5,
})

const emit = defineEmits<{
  chapterClick: [chapter: ChapterInfo]
}>()

const displayChapters = computed(() => {
  const result: ChapterInfo[] = [...props.chapters]
  while (result.length < props.totalChapters) {
    result.push({
      chapter_num: result.length + 1,
      title: `第 ${result.length + 1} 章`,
      status: 'pending',
    })
  }
  return result
})
</script>

<template>
  <div
    class="chapter-grid"
    :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }"
  >
    <div
      v-for="ch in displayChapters"
      :key="ch.chapter_num"
      class="chapter-card"
      :class="[`status-${ch.status}`, { clickable: ch.status !== 'pending' }]"
      @click="ch.status !== 'pending' && emit('chapterClick', ch)"
    >
      <div class="chapter-number">#{{ ch.chapter_num }}</div>
      <div class="chapter-title" :title="ch.title">{{ ch.title }}</div>
      <div class="chapter-meta">
        <span v-if="ch.word_count" class="word-count">{{ ch.word_count }} 字</span>
        <span v-else class="status-label">{{ statusLabel(ch.status) }}</span>
      </div>
      <div class="status-indicator">
        <div v-if="ch.status === 'generating'" class="pulse-ring"></div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待生成',
    generating: '生成中...',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}
</script>

<style scoped>
@import '@/styles/glassmorphism.css';

.chapter-grid {
  display: grid;
  gap: 12px;
}

.chapter-card {
  position: relative;
  background: var(--bg-glass);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-glass);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  cursor: default;
  transition: all var(--transition-normal);
  overflow: hidden;
}

.chapter-card.clickable {
  cursor: pointer;
}

.chapter-card:hover {
  border-color: var(--border-glow);
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow);
}

/* Status styles */
.chapter-card.status-pending {
  opacity: 0.6;
  border-color: rgba(100, 116, 139, 0.3);
}

.chapter-card.status-generating {
  border-color: var(--accent-cyan);
  box-shadow: 0 0 20px rgba(6, 182, 212, 0.2), inset 0 0 20px rgba(6, 182, 212, 0.05);
  animation: glow-pulse 2s ease-in-out infinite;
}

.chapter-card.status-completed {
  border-color: rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.05);
}

.chapter-card.status-completed:hover {
  border-color: var(--accent-emerald);
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.2);
}

.chapter-card.status-failed {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.05);
}

@keyframes glow-pulse {
  0%, 100% {
    box-shadow: 0 0 15px rgba(6, 182, 212, 0.15), inset 0 0 15px rgba(6, 182, 212, 0.03);
  }
  50% {
    box-shadow: 0 0 25px rgba(6, 182, 212, 0.3), inset 0 0 25px rgba(6, 182, 212, 0.07);
  }
}

.chapter-number {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 4px;
  letter-spacing: 0.05em;
}

.status-generating .chapter-number {
  color: var(--accent-cyan);
}

.status-completed .chapter-number {
  color: var(--accent-emerald);
}

.chapter-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chapter-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.word-count {
  color: var(--accent-emerald);
}

.status-label {
  font-style: italic;
}

.status-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
}

.pulse-ring {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent-cyan);
  animation: pulse-ring 1.5s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}
</style>
