<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { logError } from '@/utils/logger'
import { InfoFilled, Check, VideoPlay, Refresh } from '@element-plus/icons-vue'

// 类型定义
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

// 状态
const route = useRoute()
const taskId = computed(() => route.params.taskId as string)

const novelInfo = ref<NovelInfo | null>(null)
const chapters = ref<Chapter[]>([])
const loading = ref(false)
const currentChapter = ref<Chapter | null>(null)

// 获取小说信息
const fetchNovelInfo = async () => {
  loading.value = true
  try {
    const [infoResponse, chaptersResponse] = await Promise.all([
      api.getTask(taskId.value),
      api.getChapters(taskId.value)
    ])

    const taskData = infoResponse
    if (taskData) {
      novelInfo.value = {
        task_id: taskData.task_id,
        title: taskData.title || '未命名小说',
        genre: taskData.genre,
        description: taskData.description,
        chapters_count: Number(taskData.chapters) || 0,
        total_word_count: 0,
        status: taskData.status,
        created_at: taskData.created_at,
      }
    }

    // 获取章节列表
    if (chaptersResponse && chaptersResponse.chapters) {
      chapters.value = chaptersResponse.chapters
    }
  } catch (error) {
    logError('获取小说信息失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取章节内容
const fetchChapterContent = async (chapterNum: number) => {
  try {
    const response = await api.getChapterContent(taskId.value, chapterNum)

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

// 获取所有章节列表
const getAllChapters = (): Chapter[] => {
  return chapters.value
}

// 初始化
onMounted(() => {
  fetchNovelInfo()
})

// 计算属性
const chapterList = computed(() => {
  return getAllChapters()
})

const progressPercentage = computed(() => {
  if (!novelInfo.value) return 0
  if (novelInfo.value.status === 'completed') return 100
  return chapterList.value.filter(c => c.content).length / chapterList.value.length * 100
})

// 章节选中
const selectChapter = async (chapter: Chapter) => {
  // 使用 chapter_num 获取章节内容
  const chapterNum = chapter.chapter_num || 1
  await fetchChapterContent(chapterNum)
  currentChapter.value = chapter
}
</script>

<template>
  <div class="novel-preview-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner">
        <svg class="spinner" viewBox="0 0 50 50">
          <circle cx="25" cy="25" r="20" fill="none" stroke-width="4" />
        </svg>
        <span class="loading-text">加载中...</span>
      </div>
    </div>

    <!-- 小说信息 -->
    <div v-else-if="novelInfo" class="novel-info">
      <!-- 标题区域 -->
      <div class="title-section">
        <h1 class="novel-title">{{ novelInfo.title }}</h1>
        <div class="novel-meta">
          <el-tag type="primary" size="default" class="mr-2">
            {{ novelInfo.genre }}
          </el-tag>
          <span class="text-gray-600">
            {{ novelInfo.status === 'completed' ? '已完成' : '生成中' }}
          </span>
          <span class="text-gray-600">
            {{ chapterList.filter(c => c.content).length }}/{{ novelInfo.chapters_count }} 章
          </span>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="progress-section">
        <div class="flex justify-between mb-2">
          <span class="text-sm text-gray-600">生成进度</span>
          <span class="text-sm text-primary font-medium">{{ Math.round(progressPercentage) }}%</span>
        </div>
        <el-progress
          :percentage="progressPercentage"
          :status="novelInfo.status === 'failed' ? 'exception' : null"
        />
      </div>

      <!-- 描述 -->
      <el-card class="description-card" shadow="hover" v-if="novelInfo.description">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>故事描述</span>
          </div>
        </template>
        <div class="description-text">
          {{ novelInfo.description }}
        </div>
      </el-card>

      <!-- 章节列表 -->
      <div class="chapters-section">
        <div class="section-header">
          <h3>章节列表</h3>
          <span class="text-sm text-gray-600">
            {{ chapterList.length }} 个章节
          </span>
        </div>

        <el-scrollbar height="500px">
          <div class="chapter-list">
            <div
              v-for="chapter in chapterList"
              :key="chapter.chapter_id"
              class="chapter-item"
              :class="{ active: currentChapter?.chapter_id === chapter.chapter_id }"
              @click="selectChapter(chapter)"
            >
              <div class="chapter-number">
                <el-icon><VideoPlay /></el-icon>
                <span>{{ chapter.chapter_id }}</span>
              </div>
              <div class="chapter-title">
                {{ chapter.title }}
              </div>
              <div class="chapter-status">
                <el-icon v-if="chapter.content" :color="'#67c23a'">
                  <Check />
                </el-icon>
                <span class="text-gray-400">
                  {{ chapter.content ? '已生成' : '待生成' }}
                </span>
              </div>
            </div>
          </div>
        </el-scrollbar>
      </div>
    </div>

    <!-- 章节阅读区域 -->
    <div v-if="currentChapter" class="reading-section">
      <el-card shadow="hover" class="reading-card">
        <div slot="header" class="reading-header">
          <h3>{{ currentChapter.title }}</h3>
          <el-button type="primary" size="small" @click="fetchChapterContent(currentChapter.chapter_num || 1)">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>

        <div class="reading-content">
          <div v-html="currentChapter.content" class="content-text" />
        </div>

        <div class="reading-footer">
          <div class="chapter-stats">
            <span>字数: {{ currentChapter.word_count || 0 }} 字</span>
            <span>生成时间: {{ new Date(currentChapter.created_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.novel-preview-view {
  padding: 20px 0;
  height: 100%;
}

.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 500px;
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  stroke: var(--el-color-primary);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.novel-info {
  margin-bottom: 20px;
}

.title-section {
  margin-bottom: 20px;
}

.novel-title {
  font-size: 2em;
  font-weight: bold;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
}

.novel-meta {
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-section {
  margin-bottom: 24px;
}

.description-card {
  margin-bottom: 24px;
}

.description-text {
  line-height: 1.8;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
}

.chapters-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chapter-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.chapter-item:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.chapter-item.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.chapter-number {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--el-color-primary);
  margin-right: 16px;
}

.chapter-title {
  flex: 1;
  color: var(--el-text-color-primary);
}

.chapter-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reading-section {
  margin-bottom: 20px;
}

.reading-card {
  height: 600px;
  display: flex;
  flex-direction: column;
}

.reading-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.reading-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: var(--el-bg-color);
  border-radius: 8px;
  margin: 16px 0;
}

.content-text {
  line-height: 1.8;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
}

.chapter-stats {
  display: flex;
  gap: 24px;
  padding: 12px 24px;
  background: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
</style>
