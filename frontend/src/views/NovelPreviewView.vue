<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import apiV2 from '@/services/api-v2'
import { logError } from '@/utils/logger'
import { InfoFilled, Check, VideoPlay, Refresh, Reading } from '@element-plus/icons-vue'

interface Chapter {
  chapter_id: string
  chapter_num: number
  title: string
  content: string
  word_count: number
  created_at: string
}

interface NovelInfo {
  task_id: string
  title: string
  genre: string
  description: string
  chapters_count: number
  total_word_count: number
  status: string
  created_at: string
}

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

const route = useRoute()
const taskId = computed(() => route.params.taskId as string)

const novelInfo = ref<NovelInfo | null>(null)
const chapters = ref<Chapter[]>([])
const loading = ref(false)
const currentChapter = ref<Chapter | null>(null)

const fetchNovelInfo = async () => {
  loading.value = true
  try {
    const infoResponse = await apiV2.getTask(taskId.value)
    let chaptersResponse = null
    try {
      chaptersResponse = await apiV2.getChapters(taskId.value)
    } catch {
      // 任务正在执行中，章节尚未生成 —— 正常状态
    }

    const taskData = infoResponse
    if (taskData) {
      const rawGenre = taskData.genre || ''
      const genreInfo = genreMap[rawGenre] || { label: rawGenre, icon: '📖' }
      novelInfo.value = {
        task_id: taskData.task_id,
        title: taskData.title || '未命名小说',
        genre: `${genreInfo.icon} ${genreInfo.label}`,
        description: taskData.description,
        chapters_count: Number(taskData.chapters) || 0,
        total_word_count: chaptersResponse?.total_word_count || 0,
        status: taskData.status,
        created_at: taskData.created_at,
      }
    }

    if (chaptersResponse && chaptersResponse.chapters) {
      chapters.value = chaptersResponse.chapters as Chapter[]
    }
  } catch (error) {
    logError('获取小说信息失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchChapterContent = async (chapterNum: number) => {
  try {
    const response = await apiV2.getChapterContent(taskId.value, chapterNum)
    if (response) {
      currentChapter.value = {
        chapter_id: response.chapter_id,
        chapter_num: chapterNum,
        title: response.title,
        content: response.content,
        word_count: response.word_count,
        created_at: response.created_at,
      }
    }
  } catch (error) {
    logError('获取章节内容失败:', error)
  }
}

const getAllChapters = (): Chapter[] => chapters.value

onMounted(() => { fetchNovelInfo() })

const chapterList = computed(() => getAllChapters())

const progressPercentage = computed(() => {
  if (!novelInfo.value) return 0
  if (novelInfo.value.status === 'completed') return 100
  return chapterList.value.filter(c => c.content).length / Math.max(chapterList.value.length, 1) * 100
})

const selectChapter = async (chapter: Chapter) => {
  const chapterNum = chapter.chapter_num || 1
  await fetchChapterContent(chapterNum)
  currentChapter.value = chapter
}
</script>

<template>
  <div class="novel-preview-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-section">
      <div class="glass-card loading-card">
        <div class="spinner"></div>
        <span class="loading-text">加载小说数据...</span>
      </div>
    </div>

    <!-- 主内容 -->
    <template v-else-if="novelInfo">
      <!-- 页面标题 -->
      <div class="page-header">
        <div class="header-icon">
          <el-icon :size="24"><Reading /></el-icon>
        </div>
        <div>
          <h1 class="page-title">{{ novelInfo.title }}</h1>
          <p class="page-desc">{{ novelInfo.description || novelInfo.genre }}</p>
        </div>
        <div class="header-meta">
          <el-tag type="primary" effect="dark" size="small">{{ novelInfo.genre }}</el-tag>
          <el-tag
            :type="novelInfo.status === 'completed' ? 'success' : 'warning'"
            effect="dark"
            size="small"
          >
            {{ novelInfo.status === 'completed' ? '已完成' : '生成中' }}
          </el-tag>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="glass-card progress-card">
        <div class="progress-header">
          <span>生成进度</span>
          <span class="progress-pct">{{ Math.round(progressPercentage) }}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercentage + '%' }"></div>
        </div>
        <div class="progress-stats">
          <span>{{ chapterList.filter(c => c.content).length }}/{{ novelInfo.chapters_count }} 章</span>
          <span>{{ novelInfo.total_word_count || 0 }} 字</span>
        </div>
      </div>

      <!-- 描述 -->
      <div v-if="novelInfo.description" class="glass-card desc-card">
        <div class="desc-header">
          <el-icon :size="16"><InfoFilled /></el-icon>
          <span>故事描述</span>
        </div>
        <p class="desc-text">{{ novelInfo.description }}</p>
      </div>

      <!-- 主体区域：章节列表 + 阅读 -->
      <div class="main-area">
        <!-- 章节列表 -->
        <div class="glass-card chapters-card">
          <div class="section-title">章节列表 ({{ chapterList.length }})</div>
          <div class="chapter-list">
            <div
              v-for="(chapter, index) in chapterList"
              :key="chapter.chapter_id"
              class="chapter-item glass-card"
              :class="{ active: currentChapter?.chapter_id === chapter.chapter_id }"
              @click="selectChapter(chapter)"
            >
              <div class="chapter-num">
                <el-icon :size="14"><VideoPlay /></el-icon>
                <span>第 {{ chapter.chapter_num || index + 1 }} 章</span>
              </div>
              <div class="chapter-title">{{ chapter.title }}</div>
              <div class="chapter-status">
                <el-icon v-if="chapter.content" color="#34d399" :size="16"><Check /></el-icon>
                <span :class="chapter.content ? 'done' : 'pending'">
                  {{ chapter.content ? '已生成' : '待生成' }}
                </span>
              </div>
            </div>
            <div v-if="chapterList.length === 0" class="empty-list">暂无章节数据</div>
          </div>
        </div>

        <!-- 阅读区域 -->
        <div v-if="currentChapter" class="glass-card reading-card">
          <div class="reading-header">
            <h3>{{ currentChapter.title }}</h3>
            <el-button size="small" text @click="fetchChapterContent(currentChapter.chapter_num || 1)">
              <el-icon :size="14"><Refresh /></el-icon> 刷新
            </el-button>
          </div>
          <div class="reading-content">
            <div class="content-text">{{ currentChapter.content }}</div>
          </div>
          <div class="reading-footer">
            <span>字数: {{ currentChapter.word_count || 0 }} 字</span>
            <span>{{ new Date(currentChapter.created_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>

        <!-- 未选择章节提示 -->
        <div v-else class="glass-card placeholder-card">
          <el-icon :size="48" color="#475569"><Reading /></el-icon>
          <p>请从左侧选择一个章节开始阅读</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.novel-preview-view {
  max-width: 1400px;
  margin: 0 auto;
}

/* 页面标题 */
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.header-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3);
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0;
  letter-spacing: -0.5px;
}

.page-desc {
  color: #94a3b8;
  font-size: 0.875rem;
  margin: 4px 0 0;
  max-width: 500px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-meta {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

/* 加载状态 */
.loading-section {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.loading-card {
  padding: 48px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(56, 189, 248, 0.1);
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: #94a3b8;
  font-size: 0.9375rem;
}

/* 进度卡片 */
.progress-card {
  padding: 20px;
  margin-bottom: 20px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  color: #94a3b8;
  font-size: 0.875rem;
}

.progress-pct {
  color: #38bdf8;
  font-weight: 600;
}

.progress-track {
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 99px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #06b6d4, #3b82f6);
  border-radius: 99px;
  transition: width 0.5s ease;
}

.progress-stats {
  display: flex;
  gap: 24px;
  font-size: 0.8125rem;
  color: #64748b;
}

/* 描述卡片 */
.desc-card {
  padding: 20px;
  margin-bottom: 20px;
}

.desc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 12px;
}

.desc-text {
  color: #cbd5e1;
  line-height: 1.8;
  margin: 0;
  white-space: pre-wrap;
}

/* 主体区域 */
.main-area {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: start;
}

/* 章节列表卡片 */
.chapters-card {
  padding: 20px;
}

.section-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 16px;
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 600px;
  overflow-y: auto;
}

.chapter-item {
  padding: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chapter-item:hover {
  border-color: rgba(56, 189, 248, 0.3);
  transform: translateX(2px);
}

.chapter-item.active {
  border-color: rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.08);
}

.chapter-num {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #38bdf8;
}

.chapter-title {
  font-size: 0.875rem;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chapter-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
}

.chapter-status .done { color: #34d399; }
.chapter-status .pending { color: #64748b; }

.empty-list {
  padding: 32px;
  text-align: center;
  color: #64748b;
  font-size: 0.875rem;
}

/* 阅读卡片 */
.reading-card {
  padding: 24px;
  min-height: 400px;
  display: flex;
  flex-direction: column;
}

.reading-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.reading-header h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #f8fafc;
  margin: 0;
}

.reading-content {
  flex: 1;
  overflow-y: auto;
}

.content-text {
  line-height: 2;
  color: #e2e8f0;
  white-space: pre-wrap;
  font-size: 1rem;
  font-family: 'Georgia', 'Noto Serif SC', serif;
}

.reading-footer {
  display: flex;
  gap: 24px;
  padding-top: 16px;
  margin-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  color: #64748b;
  font-size: 0.8125rem;
}

/* 占位提示 */
.placeholder-card {
  padding: 80px 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #475569;
  font-size: 0.9375rem;
}
</style>
