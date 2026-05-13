<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import apiV2, { connectSSE, type SSEEvent } from '@/services/api-v2'
import ChapterProgressGrid, { type ChapterInfo } from '@/components/ChapterProgressGrid.vue'
import GenerationTimeline, { type TimelineStage } from '@/components/GenerationTimeline.vue'
import GenerationStats, { type GenerationStatsData } from '@/components/GenerationStats.vue'
import DagVisualizer from '@/components/DagVisualizer.vue'
import type { DagNode, DagEdge } from '@/components/DagVisualizer.vue'
import { Connection, Warning, ArrowLeft, Download } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

const taskId = computed(() => route.params.taskId as string)

// Connection state
const sseConnected = ref(false)
const loading = ref(true)
const error = ref<string | null>(null)
let disconnectSSE: (() => void) | null = null

// Genre label map (value -> { label, icon })
const genreMap: Record<string, { label: string; icon: string }> = {
  fantasy: { label: '奇幻', icon: '✨' },
  'sci-fi': { label: '科幻', icon: '🚀' },
  wuxia: { label: '武侠', icon: '⚔️' },
  xianxia: { label: '修仙', icon: '☯️' },
  romance: { label: '言情', icon: '💕' },
  mystery: { label: '悬疑', icon: '🔍' },
  horror: { label: '灵异', icon: '👻' },
  thriller: { label: '惊悚', icon: '🔥' },
  history: { label: '历史', icon: '📜' },
  adventure: { label: '冒险', icon: '🌊' },
  drama: { label: '剧情', icon: '🎭' },
  urban_fantasy: { label: '都市', icon: '🏙️' },
  other: { label: '其他', icon: '📖' },
}

// Live content preview
const liveContent = ref('')
const liveContentChapter = ref<number | null>(null)
const showContentPanel = ref(false)

// Live generation logs
interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'success' | 'error' | 'debug'
  message: string
  agent?: string
  detail?: string
}
const generationLogs = ref<LogEntry[]>([])
let logIdCounter = 0
const logContainerRef = ref<HTMLElement | null>(null)

// Auto-scroll log panel on new entries
watch(generationLogs, () => {
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
}, { flush: 'post' })

// Task detail
const taskDetail = ref<any>(null)
const novelTitle = ref('')
const novelGenre = ref('')
const novelGenreIcon = ref('📖')
const optimizedConfig = ref<{ style: string; target_audience: string; description: string; chapters: number; word_count: number } | null>(null)

// Computed genre display with icon
const genreDisplay = computed(() => {
  if (!novelGenre.value) return ''
  return `${novelGenreIcon.value} ${novelGenre.value}`
})

// Chapter progress state
const chapters = ref<ChapterInfo[]>([])
const totalChapters = ref(20)

// Stats state
const stats = ref<GenerationStatsData>({
  total_words: 0,
  target_words: 0,
  chapters_completed: 0,
  total_chapters: 20,
  elapsed_seconds: 0,
  eta_seconds: undefined,
  speed_wpm: undefined,
})

// Timeline state
const timelineStages = ref<TimelineStage[]>([
  { id: 'config_enhancer', label: '配置增强', status: 'pending' },
  { id: 'outline_planner', label: '大纲规划', status: 'pending' },
  { id: 'character_generator', label: '角色生成', status: 'pending' },
  { id: 'world_builder', label: '世界构建', status: 'pending' },
  { id: 'content_generator', label: '内容生成', status: 'pending' },
  { id: 'quality_checker', label: '质量检查', status: 'pending' },
])

const currentTimelineStage = ref<string | null>(null)

// DAG mini visualization
const dagEdges: DagEdge[] = [
  { source: 'config_enhancer', target: 'outline_planner' },
  { source: 'outline_planner', target: 'character_generator' },
  { source: 'outline_planner', target: 'world_builder' },
  { source: 'character_generator', target: 'content_generator' },
  { source: 'world_builder', target: 'content_generator' },
  { source: 'content_generator', target: 'quality_checker' },
]

const dagNodes = computed<DagNode[]>(() => {
  return timelineStages.value.map(s => ({
    id: s.id,
    label: s.label,
    status: s.status as DagNode['status'],
  }))
})

const activeNodeId = computed(() => {
  const running = dagNodes.value.find(n => n.status === 'running')
  return running?.id || null
})

// LLM activity
const llmActivity = ref<{
  provider: string
  model: string
  status: 'requesting' | 'streaming' | 'done' | 'error'
  stage?: string
} | null>(null)

// Overall progress
const overallProgress = computed(() => {
  if (!totalChapters.value) return 0
  return Math.round((stats.value.chapters_completed / totalChapters.value) * 100)
})

const taskStatus = ref<'pending' | 'running' | 'completed' | 'failed'>('pending')

function handleSSEEvent(event: SSEEvent) {
  const payload = event.payload || {}

  switch (event.type) {
    case 'task.progress': {
      // Update stage statuses
      const stageStatuses: Record<string, { status: string; elapsed: number }> = payload.stage_statuses || {}
      for (const stage of timelineStages.value) {
        const info = stageStatuses[stage.id]
        if (info) {
          stage.status = info.status === 'running' || info.status === 'executing' ? 'running'
            : info.status === 'completed' ? 'completed'
            : info.status === 'failed' ? 'failed'
            : 'pending'
          stage.elapsed_seconds = info.elapsed || 0
        }
      }
      currentTimelineStage.value = payload.current_stage || null

      // Update chapters info
      if (payload.chapters) {
        totalChapters.value = payload.chapters.total || totalChapters.value
        stats.value.chapters_completed = payload.chapters.completed || 0
      }

      // Update overall progress
      stats.value.elapsed_seconds = payload.elapsed_seconds || 0
      break
    }

    case 'chapter.started': {
      const chNum = payload.chapter_num
      if (chNum) {
        const idx = chapters.value.findIndex(c => c.chapter_num === chNum)
        if (idx >= 0) {
          chapters.value[idx].status = 'generating'
        } else {
          chapters.value.push({
            chapter_num: chNum,
            title: `第 ${chNum} 章`,
            status: 'generating',
          })
        }
      }
      // Update content_generator stage to running
      const cgStage = timelineStages.value.find(s => s.id === 'content_generator')
      if (cgStage && cgStage.status === 'pending') {
        cgStage.status = 'running'
      }
      break
    }

    case 'chapter.completed': {
      const chNumC = payload.chapter_num
      if (chNumC) {
        const idx = chapters.value.findIndex(c => c.chapter_num === chNumC)
        const wordCount = payload.word_count || 0
        if (idx >= 0) {
          chapters.value[idx].status = 'completed'
          chapters.value[idx].word_count = wordCount
        } else {
          chapters.value.push({
            chapter_num: chNumC,
            title: `第 ${chNumC} 章`,
            status: 'completed',
            word_count: wordCount,
          })
        }
        stats.value.total_words += wordCount
        stats.value.chapters_completed = chapters.value.filter(c => c.status === 'completed').length
      }
      // 保存内容预览
      if (payload.content_preview) {
        liveContent.value = payload.content_preview
        showContentPanel.value = true
      }
      break
    }

    case 'chapter.content': {
      const chNumContent = payload.chapter_num
      if (chNumContent) {
        liveContentChapter.value = chNumContent
        liveContent.value = payload.content || ''
        showContentPanel.value = true
      }
      break
    }

    case 'generation.log': {
      const entry: LogEntry = {
        id: ++logIdCounter,
        timestamp: new Date().toLocaleTimeString(),
        level: payload.level || 'info',
        message: payload.message || '',
        agent: payload.agent,
        detail: payload.detail || payload.error,
      }
      generationLogs.value.push(entry)
      // 保留最近500条日志，防止内存溢出
      if (generationLogs.value.length > 500) {
        generationLogs.value = generationLogs.value.slice(-500)
      }
      break
    }

    case 'agent.started':
    case 'agent.completed':
    case 'agent.failed': {
      const agentName = payload.agent || event.source
      const stage = timelineStages.value.find(s => s.id === agentName)
      if (stage) {
        if (event.type === 'agent.started') stage.status = 'running'
        else if (event.type === 'agent.completed') stage.status = 'completed'
        else if (event.type === 'agent.failed') stage.status = 'failed'
      }
      break
    }

    case 'task.created':
    case 'task.started': {
      taskStatus.value = 'running'
      break
    }

    case 'task.completed': {
      taskStatus.value = 'completed'
      break
    }

    case 'task.failed': {
      taskStatus.value = 'failed'
      error.value = payload.error || '任务失败'
      break
    }

    case 'task.cancelled': {
      taskStatus.value = 'failed'
      error.value = '任务已取消'
      break
    }

    case 'llm.request': {
      llmActivity.value = {
        provider: payload.provider || 'unknown',
        model: payload.model || 'unknown',
        status: 'requesting',
        stage: payload.stage,
      }
      break
    }

    case 'llm.response': {
      if (llmActivity.value) {
        llmActivity.value.status = payload.streaming ? 'streaming' : 'done'
      }
      break
    }

    case 'llm.error': {
      if (llmActivity.value) {
        llmActivity.value.status = 'error'
      }
      break
    }
  }
}

async function loadTaskDetail() {
  try {
    const detail = await taskStore.getTaskDetail(taskId.value)
    if (detail) {
      taskDetail.value = detail
      novelTitle.value = detail.title || detail.payload?.title || '未命名小说'
      const rawGenre = detail.genre || detail.payload?.genre || ''
      const genreInfo = genreMap[rawGenre] || { label: rawGenre, icon: '📖' }
      novelGenre.value = genreInfo.label
      novelGenreIcon.value = genreInfo.icon
      totalChapters.value = detail.chapters || detail.payload?.chapters || 20

      // 读取经过 Agent 优化后的配置信息
      optimizedConfig.value = {
        style: detail.style || detail.payload?.style || 'light',
        target_audience: detail.target_audience || detail.payload?.target_audience || 'general',
        description: detail.description || detail.payload?.description || '',
        chapters: detail.chapters || detail.payload?.chapters || 20,
        word_count: detail.word_count_per_chapter || detail.payload?.word_count_per_chapter || 2000,
      }

      // 设置任务状态
      taskStatus.value = detail.status || 'pending'

      // Initialize chapter grid
      initChapters()

      // Load any existing progress
      if (detail.stage_statuses) {
        for (const stage of timelineStages.value) {
          const info = detail.stage_statuses[stage.id]
          if (info) {
            stage.status = info.status === 'running' || info.status === 'executing' ? 'running'
              : info.status === 'completed' ? 'completed'
              : info.status === 'failed' ? 'failed'
              : 'pending'
            stage.elapsed_seconds = info.elapsed || 0
          }
        }
      }
      if (detail.progress !== undefined) {
        stats.value.chapters_completed = detail.chapters?.completed || 0
        stats.value.total_words = detail.chapters?.total_words || 0
      }
    }
  } catch (e: any) {
    error.value = e.message || '加载任务详情失败'
  } finally {
    loading.value = false
  }
}

function initChapters() {
  const arr: ChapterInfo[] = []
  for (let i = 1; i <= totalChapters.value; i++) {
    // Check for existing completed chapters from task detail
    const existing = taskDetail.value?.chapters?.completed_list?.find((c: any) => c.chapter_num === i)
    arr.push({
      chapter_num: i,
      title: existing?.title || `第 ${i} 章`,
      word_count: existing?.word_count,
      status: existing ? 'completed' : 'pending',
    })
  }
  chapters.value = arr
  stats.value.chapters_completed = arr.filter(c => c.status === 'completed').length
  stats.value.total_chapters = totalChapters.value
}

function onChapterClick(chapter: ChapterInfo) {
  // Navigate to preview or show chapter detail
  if (chapter.status === 'completed') {
    router.push(`/tasks/preview/${taskId.value}?chapter=${chapter.chapter_num}`)
  }
}

function goBack() {
  router.push('/tasks/dashboard')
}

onMounted(() => {
  loadTaskDetail()

  // Connect SSE
  disconnectSSE = connectSSE(
    handleSSEEvent,
    () => { sseConnected.value = false },
    () => { sseConnected.value = true },
    () => { sseConnected.value = false },
  )
})

onUnmounted(() => {
  if (disconnectSSE) disconnectSSE()
})
</script>

<template>
  <div class="generation-view">
    <!-- Header -->
    <div class="page-header">
      <button class="back-btn" @click="goBack">
        <el-icon :size="18"><ArrowLeft /></el-icon>
      </button>
      <div class="header-info">
        <h1 class="novel-title">{{ novelTitle || '加载中...' }}</h1>
        <p class="novel-meta">
          <span v-if="novelGenre" class="genre-tag">{{ genreDisplay }}</span>
          <span v-if="taskDetail?.task_id" class="task-id">ID: {{ taskId }}</span>
        </p>
      </div>
      <div class="header-actions">
        <div class="connection-status" :class="{ connected: sseConnected }">
          <span class="status-dot"></span>
          {{ sseConnected ? '实时' : '连接中...' }}
        </div>
        <el-tag v-if="taskStatus === 'completed'" type="success" size="large" effect="dark">已完成</el-tag>
        <el-tag v-else-if="taskStatus === 'failed'" type="danger" size="large" effect="dark">失败</el-tag>
        <el-tag v-else-if="taskStatus === 'running'" type="primary" size="large" effect="dark">生成中</el-tag>
        <el-tag v-else type="info" size="large" effect="dark">等待中</el-tag>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state glass-card">
      <el-icon :size="48" color="#ef4444"><Warning /></el-icon>
      <h2>加载失败</h2>
      <p>{{ error }}</p>
      <button class="glass-btn" @click="loadTaskDetail">重试</button>
    </div>

    <!-- Main content -->
    <template v-else>
      <!-- Overall progress bar -->
      <div class="overall-progress glass-card">
        <div class="progress-header">
          <span class="progress-title">总体生成进度</span>
          <span class="progress-percent">{{ overallProgress }}%</span>
        </div>
        <div class="glass-progress">
          <div
            class="glass-progress-bar"
            :style="{ width: `${overallProgress}%` }"
          ></div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="stats-section">
        <GenerationStats :stats="stats" />
      </div>

      <!-- Optimized Config Info -->
      <div v-if="optimizedConfig" class="glass-card config-info-card">
        <div class="card-header">
          <span class="card-title">Agent 优化配置</span>
        </div>
        <div class="config-grid">
          <div class="config-item">
            <span class="config-label">风格</span>
            <span class="config-value">{{ optimizedConfig.style }}</span>
          </div>
          <div class="config-item">
            <span class="config-label">目标读者</span>
            <span class="config-value">{{ optimizedConfig.target_audience }}</span>
          </div>
          <div class="config-item">
            <span class="config-label">章节数</span>
            <span class="config-value">{{ optimizedConfig.chapters }} 章</span>
          </div>
          <div class="config-item">
            <span class="config-label">每章字数</span>
            <span class="config-value">{{ optimizedConfig.word_count }} 字</span>
          </div>
          <div v-if="optimizedConfig.description" class="config-item description">
            <span class="config-label">小说描述</span>
            <span class="config-value">{{ optimizedConfig.description }}</span>
          </div>
        </div>
      </div>

      <!-- Two column: DAG + Timeline | Chapter Grid -->
      <div class="main-grid">
        <!-- Left: DAG mini + Timeline -->
        <div class="left-panel">
          <!-- DAG mini visualization -->
          <div class="glass-card dag-card">
            <div class="card-header">
              <span class="card-title">工作流 DAG</span>
            </div>
            <DagVisualizer
              :nodes="dagNodes"
              :edges="dagEdges"
              :width="400"
              :height="200"
              :active-node-id="activeNodeId"
            />
          </div>

          <!-- Timeline -->
          <div class="glass-card timeline-card">
            <div class="card-header">
              <span class="card-title">阶段时间线</span>
            </div>
            <GenerationTimeline
              :stages="timelineStages"
              :current-stage-id="currentTimelineStage"
            />
          </div>

          <!-- LLM Activity -->
          <div class="glass-card llm-card">
            <div class="card-header">
              <span class="card-title">LLM 活动</span>
            </div>
            <div v-if="llmActivity" class="llm-info">
              <div class="llm-row">
                <span class="llm-label">Provider:</span>
                <span class="llm-value">{{ llmActivity.provider }}</span>
              </div>
              <div class="llm-row">
                <span class="llm-label">Model:</span>
                <span class="llm-value">{{ llmActivity.model }}</span>
              </div>
              <div class="llm-row">
                <span class="llm-label">状态:</span>
                <el-tag
                  :type="llmActivity.status === 'done' ? 'success' : llmActivity.status === 'error' ? 'danger' : 'warning'"
                  size="small"
                >
                  {{ llmActivity.status === 'requesting' ? '请求中' : llmActivity.status === 'streaming' ? '流式输出' : llmActivity.status === 'done' ? '完成' : '错误' }}
                </el-tag>
              </div>
            </div>
            <div v-else class="llm-empty">
              <p>等待 LLM 调用...</p>
            </div>
          </div>
        </div>

        <!-- Right: Chapter grid -->
        <div class="right-panel">
          <div class="glass-card chapter-section">
            <div class="card-header">
              <span class="card-title">章节生成状态</span>
              <span class="chapter-count">
                {{ stats.chapters_completed }} / {{ totalChapters }} 章
              </span>
            </div>
            <ChapterProgressGrid
              :chapters="chapters"
              :total-chapters="totalChapters"
              :columns="5"
              @chapter-click="onChapterClick"
            />
          </div>
        </div>
      </div>

      <!-- Live content preview -->
      <div v-if="showContentPanel" class="glass-card live-content-card">
        <div class="card-header">
          <span class="card-title">
            <el-icon :size="16"><Connection /></el-icon>
            实时内容
            <span v-if="liveContentChapter" class="content-chapter-label">第 {{ liveContentChapter }} 章</span>
          </span>
          <button class="glass-btn-sm" @click="showContentPanel = false">关闭</button>
        </div>
        <div class="live-content-body">
          <pre class="content-text">{{ liveContent || '等待生成...' }}</pre>
        </div>
      </div>

      <!-- Live generation logs -->
      <div class="glass-card live-log-card">
        <div class="card-header">
          <span class="card-title">
            <el-icon :size="16"><Warning /></el-icon>
            生成日志
          </span>
          <div class="log-actions">
            <span class="log-count">{{ generationLogs.length }} 条</span>
            <button
              v-if="generationLogs.length > 0"
              class="glass-btn-sm"
              @click="generationLogs = []"
            >清空</button>
          </div>
        </div>
        <div class="live-log-body" ref="logContainerRef">
          <div v-if="generationLogs.length === 0" class="log-empty">
            等待生成日志...
          </div>
          <div
            v-for="log in generationLogs"
            :key="log.id"
            class="log-entry"
            :class="`log-${log.level}`"
          >
            <span class="log-time">{{ log.timestamp }}</span>
            <span class="log-level">{{ log.level }}</span>
            <span v-if="log.agent" class="log-agent">[{{ log.agent }}]</span>
            <span class="log-msg">{{ log.message }}</span>
            <span v-if="log.detail" class="log-detail">{{ log.detail }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.generation-view {
  max-width: 1400px;
  margin: 0 auto;
}

/* Page Header */
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.back-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--bg-glass);
  border: 1px solid var(--border-glass);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-normal);
  flex-shrink: 0;
}

.back-btn:hover {
  border-color: var(--border-glow);
  box-shadow: var(--shadow-glow);
}

.header-info {
  flex: 1;
  min-width: 0;
}

.novel-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.5px;
}

.novel-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}

.genre-tag {
  font-size: 0.8125rem;
  color: var(--accent-cyan);
  background: rgba(6, 182, 212, 0.1);
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

.task-id {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: monospace;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-muted);
  padding: 4px 12px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.05);
}

.connection-status.connected {
  color: var(--accent-emerald);
  background: rgba(16, 185, 129, 0.1);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
}

.connection-status.connected .status-dot {
  background: var(--accent-emerald);
  animation: status-pulse 2s ease-in-out infinite;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

/* Loading / Error */
.loading-state {
  padding: 40px;
}

.error-state {
  padding: 60px 40px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.error-state h2 {
  font-size: 1.25rem;
  color: var(--text-primary);
}

.error-state p {
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Overall Progress */
.overall-progress {
  padding: 20px 24px;
  margin-bottom: 20px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

.progress-percent {
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--accent-cyan);
  font-variant-numeric: tabular-nums;
}

/* Stats section */
.stats-section {
  margin-bottom: 24px;
}

/* Two column layout */
.main-grid {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 20px;
  align-items: start;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-panel {
  min-width: 0;
}

/* Cards */
.glass-card {
  background: var(--bg-glass);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-glass);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-glass);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* DAG card */
.dag-card {
  padding: 20px;
}

/* Timeline card */
.timeline-card {
  padding: 20px;
}

/* LLM card */
.llm-card {
  padding: 20px;
}

.llm-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.llm-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8125rem;
}

.llm-label {
  color: var(--text-muted);
  min-width: 60px;
}

.llm-value {
  color: var(--text-primary);
  font-family: monospace;
}

.llm-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Chapter section */
.chapter-section {
  padding: 24px;
}

.chapter-count {
  font-size: 0.875rem;
  color: var(--accent-emerald);
  font-weight: 600;
}

/* Responsive */
/* Optimized Config Info */
.config-info-card {
  padding: 20px;
  margin-bottom: 20px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-md);
}

.config-item.description {
  grid-column: 1 / -1;
}

.config-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-value {
  font-size: 0.9375rem;
  color: var(--text-primary);
  font-weight: 500;
}

.config-item.description .config-value {
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

/* Live content preview */
.live-content-card {
  padding: 20px;
  margin-top: 20px;
}

.content-chapter-label {
  font-size: 0.75rem;
  color: var(--accent-cyan);
  background: rgba(6, 182, 212, 0.1);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  margin-left: 8px;
}

.live-content-body {
  max-height: 400px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-md);
  padding: 16px;
}

.content-text {
  font-family: 'Georgia', 'Noto Serif SC', serif;
  font-size: 0.9375rem;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}

/* Live generation logs */
.live-log-card {
  padding: 20px;
  margin-top: 16px;
}

.log-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-count {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.glass-btn-sm {
  padding: 4px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-glass);
  border: 1px solid var(--border-glass);
  color: var(--text-muted);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.glass-btn-sm:hover {
  border-color: var(--border-glow);
  color: var(--text-primary);
}

.live-log-body {
  max-height: 300px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-md);
  padding: 8px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.8125rem;
}

.log-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  line-height: 1.5;
  flex-wrap: wrap;
}

.log-entry:hover {
  background: rgba(255, 255, 255, 0.03);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
}

.log-level {
  font-size: 0.6875rem;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  flex-shrink: 0;
  min-width: 48px;
  text-align: center;
}

.log-info .log-level {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.log-success .log-level {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.log-error .log-level {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.log-debug .log-level {
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
}

.log-agent {
  color: var(--accent-cyan);
  flex-shrink: 0;
}

.log-msg {
  color: var(--text-primary);
  flex: 1;
}

.log-detail {
  color: var(--text-muted);
  width: 100%;
  padding-left: 24px;
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Responsive */
@media (max-width: 1100px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}
</style>
