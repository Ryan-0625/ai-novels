<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import apiV2 from '@/services/api-v2'
import { logError } from '@/utils/logger'
import { MagicStick, Document, Setting, Brush, InfoFilled } from '@element-plus/icons-vue'

// ── 草稿缓存 ──────────────────────────────────────────────
const DRAFT_KEY = 'novel_task_draft'

interface DraftData {
  genre: string
  title: string
  description: string
  chapters: number
  word_count_per_chapter: number
  style: string
  target_audience: string
  savedAt: number
}

const draftRestoredAt = ref<number | null>(null)
const hasDraft = computed(() => draftRestoredAt.value !== null)

const formatDraftTime = (ts: number) => {
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const saveDraft = () => {
  const draft: DraftData = {
    genre: form.genre,
    title: form.title,
    description: form.description,
    chapters: form.chapters,
    word_count_per_chapter: form.word_count_per_chapter,
    style: form.style,
    target_audience: form.target_audience,
    savedAt: Date.now(),
  }
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
}

const clearDraft = () => {
  localStorage.removeItem(DRAFT_KEY)
  draftRestoredAt.value = null
}

// ── 表单数据 ──────────────────────────────────────────────
const form = reactive({
  user_id: 'user_' + Date.now(),
  task_type: 'novel',
  genre: 'fantasy',
  title: '',
  description: '',
  chapters: 20,
  word_count_per_chapter: 3000,
  style: '',
  target_audience: 'general',
})

// LLM 模型名称（从后端配置获取）
const aiModelName = ref('deepseek-v4-flash')

const fetchModelName = async () => {
  try {
    const resp = await apiV2.getConfigItem('llm')
    if (resp?.value) {
      const llmConfig = resp.value
      const provider = llmConfig.default_provider || llmConfig.provider || 'ollama'
      const providerCfg = llmConfig.providers?.[provider] || llmConfig[provider]
      if (providerCfg?.model) {
        aiModelName.value = providerCfg.model
      } else if (llmConfig.model) {
        aiModelName.value = llmConfig.model
      }
    }
  } catch {
    // 保留默认值 'Qwen2.5-7B'
  }
}

// 从后端获取预设配置
const fetchGenres = async () => {
  try {
    const backendGenres = await apiV2.listNovelGenres()
    if (backendGenres && backendGenres.length > 0) {
      const genreIcons: Record<string, { icon: string; color: string }> = {
        fantasy: { icon: '✨', color: '#a855f7' },
        'sci-fi': { icon: '🚀', color: '#3b82f6' },
        wuxia: { icon: '⚔️', color: '#f59e0b' },
        xianxia: { icon: '☯️', color: '#8b5cf6' },
        romance: { icon: '💕', color: '#ec4899' },
        mystery: { icon: '🔍', color: '#6366f1' },
        horror: { icon: '👻', color: '#ef4444' },
        thriller: { icon: '🔥', color: '#f97316' },
        history: { icon: '📜', color: '#10b981' },
        adventure: { icon: '🌊', color: '#14b8a6' },
        drama: { icon: '🎭', color: '#06b6d4' },
        urban_fantasy: { icon: '🏙️', color: '#78716c' },
        other: { icon: '📖', color: '#6b7280' },
      }
      const merged = new Map<string, any>()
      backendGenres.forEach((g: any) => {
        const style = genreIcons[g.value] || { icon: '📖', color: '#6b7280' }
        merged.set(g.value, { label: g.label, value: g.value, icon: style.icon, color: style.color })
      })
      genreOptions.value = Array.from(merged.values())
    }
  } catch {
    // 使用本地硬编码作为后备
  }
}

const fetchPresets = async () => {
  try {
    const presets = await apiV2.listNovelPresets()
    if (presets && presets.length > 0) {
      const genreIcons: Record<string, { icon: string; color: string }> = {
        fantasy: { icon: '✨', color: '#a855f7' },
        'sci-fi': { icon: '🚀', color: '#3b82f6' },
        wuxia: { icon: '⚔️', color: '#f59e0b' },
        xianxia: { icon: '☯️', color: '#8b5cf6' },
        romance: { icon: '💕', color: '#ec4899' },
        mystery: { icon: '🔍', color: '#6366f1' },
        horror: { icon: '👻', color: '#ef4444' },
        thriller: { icon: '🔥', color: '#f97316' },
        history: { icon: '📜', color: '#10b981' },
        adventure: { icon: '🌊', color: '#14b8a6' },
        drama: { icon: '🎭', color: '#06b6d4' },
        urban_fantasy: { icon: '🏙️', color: '#78716c' },
        other: { icon: '📖', color: '#6b7280' },
      }
      const serverGenres = presets.map((p: any) => {
        const style = genreIcons[p.genre] || { icon: '📖', color: '#6b7280' }
        return { label: p.title || p.genre, value: p.genre, icon: style.icon, color: style.color }
      })
      // 合并后端预设与本地硬编码，后端优先
      const merged = new Map<string, any>()
      for (const g of genreOptions.value) merged.set(g.value, g)
      for (const g of serverGenres) merged.set(g.value, g)
      genreOptions.value = Array.from(merged.values())
    }
  } catch {
    // 使用本地硬编码的 genreOptions 作为后备
  }
}

// 从后端获取风格配置
const fetchStyles = async () => {
  try {
    const backendStyles = await apiV2.listNovelStyles()
    if (backendStyles && backendStyles.length > 0) {
      styleOptions.value = backendStyles.map((s: any) => ({
        label: s.label,
        value: s.value,
        desc: s.desc || '',
      }))
    }
  } catch {
    // 使用本地硬编码作为后备
  }
}

// 页面挂载时恢复草稿、获取预设
onMounted(() => {
  fetchGenres()
  fetchPresets()
  fetchStyles()
  fetchModelName()
  const raw = localStorage.getItem(DRAFT_KEY)
  if (!raw) return
  try {
    const draft: DraftData = JSON.parse(raw)
    // 只有有内容时才恢复（title 或 description 非空）
    if (!draft.title && !draft.description) return
    Object.assign(form, {
      genre: draft.genre ?? form.genre,
      title: draft.title ?? '',
      description: draft.description ?? '',
      chapters: draft.chapters ?? form.chapters,
      word_count_per_chapter: draft.word_count_per_chapter ?? form.word_count_per_chapter,
      style: draft.style ?? '',
      target_audience: draft.target_audience ?? form.target_audience,
    })
    draftRestoredAt.value = draft.savedAt
    ElMessage({
      message: `已恢复上次未完成的草稿（${formatDraftTime(draft.savedAt)}）`,
      type: 'info',
      duration: 3000,
      showClose: true,
    })
  } catch {
    // 损坏的缓存直接丢弃
    clearDraft()
  }
})

// 防抖：表单变化 800ms 后写入缓存（排除 user_id / task_type）
let draftTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => ({
    genre: form.genre,
    title: form.title,
    description: form.description,
    chapters: form.chapters,
    word_count_per_chapter: form.word_count_per_chapter,
    style: form.style,
    target_audience: form.target_audience,
  }),
  () => {
    if (draftTimer) clearTimeout(draftTimer)
    draftTimer = setTimeout(saveDraft, 800)
  },
  { deep: true }
)

// ── 表单验证规则 ──────────────────────────────────────────
const rules = {
  title: [
    { required: true, message: '请输入小说标题', trigger: 'blur' },
    { min: 2, max: 50, message: '标题长度在2到50个字符之间', trigger: 'blur' },
  ],
  description: [
    { required: true, message: '请输入小说描述', trigger: 'blur' },
    { min: 10, message: '描述至少10个字符', trigger: 'blur' },
  ],
}

// ── 状态 ──────────────────────────────────────────────────
const loading = ref(false)
const formRef = ref()
const router = useRouter()

// ── 可选值 ────────────────────────────────────────────────
const genreOptions = ref([
  { label: '奇幻', value: 'fantasy', icon: '✨', color: '#a855f7' },
  { label: '科幻', value: 'sci-fi', icon: '🚀', color: '#3b82f6' },
  { label: '武侠', value: 'wuxia', icon: '⚔️', color: '#f59e0b' },
  { label: '修仙', value: 'xianxia', icon: '☯️', color: '#8b5cf6' },
  { label: '言情', value: 'romance', icon: '💕', color: '#ec4899' },
  { label: '悬疑', value: 'mystery', icon: '🔍', color: '#6366f1' },
  { label: '灵异', value: 'horror', icon: '👻', color: '#ef4444' },
  { label: '惊悚', value: 'thriller', icon: '🔥', color: '#f97316' },
  { label: '历史', value: 'history', icon: '📜', color: '#10b981' },
  { label: '冒险', value: 'adventure', icon: '🌊', color: '#14b8a6' },
  { label: '剧情', value: 'drama', icon: '🎭', color: '#06b6d4' },
  { label: '都市', value: 'urban_fantasy', icon: '🏙️', color: '#78716c' },
  { label: '其他', value: 'other', icon: '📖', color: '#6b7280' },
])

const styleOptions = ref([
  { label: '轻松', value: 'light', desc: '轻松愉快的叙事风格' },
  { label: '严肃', value: 'serious', desc: '庄重严谨的叙事风格' },
  { label: '幽默', value: 'humor', desc: '诙谐幽默的叙事风格' },
  { label: '热血', value: 'passion', desc: '激情澎湃的叙事风格' },
  { label: '悬疑', value: 'suspense', desc: '紧张刺激的叙事风格' },
])

// ── 表单提交 ──────────────────────────────────────────────
const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    loading.value = true
    const response = await apiV2.createTask({
      agent_name: 'coordinator',
      payload: {
        user_id: form.user_id,
        task_type: form.task_type,
        genre: form.genre,
        title: form.title,
        description: form.description,
        chapters: form.chapters,
        word_count_per_chapter: form.word_count_per_chapter,
        style: form.style,
        target_audience: form.target_audience,
        language: localStorage.getItem('ai-novels-lang') || 'zh-CN',
      },
    })
    if (response && response.task_id) {
      clearDraft()   // 提交成功后清除草稿
      router.push(`/tasks/monitor`)
    }
  } catch (error) {
    logError('创建任务失败:', error)
  } finally {
    loading.value = false
  }
}

// ── 重置表单 ──────────────────────────────────────────────
const handleReset = () => {
  formRef.value?.resetFields()
  form.genre = 'fantasy'
  form.style = ''
  form.target_audience = 'general'
  form.chapters = 20
  form.word_count_per_chapter = 3000
  clearDraft()
  ElMessage({ message: '已清除草稿', type: 'success', duration: 2000 })
}

// ── 当前选中类型 ──────────────────────────────────────────
const selectedGenre = computed(() => genreOptions.value.find(g => g.value === form.genre))
</script>

<template>
  <div class="task-creation-view">
    <!-- 页面头部 -->
    <div class="page-header animate-fade-in">
      <div class="header-content">
        <div class="header-icon">
          <el-icon :size="28"><MagicStick /></el-icon>
        </div>
        <div class="header-text">
          <h1 class="page-title">创建小说生成任务</h1>
          <p class="page-description">填写相关信息，AI 将为您生成高质量的小说内容</p>
        </div>
        <div v-if="hasDraft" class="draft-badge">
          <span class="draft-dot"></span>
          草稿已恢复 · {{ formatDraftTime(draftRestoredAt!) }}
        </div>
      </div>
    </div>

    <div class="content-grid">
      <!-- 主表单卡片 -->
      <div class="form-section animate-fade-in" style="animation-delay: 0.1s">
        <div class="glass-card form-card">
          <div class="card-header">
            <div class="card-icon">
              <el-icon :size="20"><Document /></el-icon>
            </div>
            <span class="card-title">基本信息</span>
          </div>
          
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="form-content"
          >
            <!-- 小说标题 -->
            <el-form-item label="小说标题" prop="title">
              <el-input
                v-model="form.title"
                placeholder="请输入小说标题（如：天道图书馆）"
                clearable
                size="large"
                class="glass-input"
              >
                <template #prefix>
                  <el-icon><Document /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <!-- 类型选择 -->
            <el-form-item label="小说类型" prop="genre">
              <div class="genre-grid">
                <div
                  v-for="item in genreOptions"
                  :key="item.value"
                  class="genre-card"
                  :class="{ active: form.genre === item.value }"
                  @click="form.genre = item.value"
                >
                  <span class="genre-icon">{{ item.icon }}</span>
                  <span class="genre-label">{{ item.label }}</span>
                  <div class="genre-glow" :style="{ background: item.color }"></div>
                </div>
              </div>
            </el-form-item>

            <!-- 描述 -->
            <el-form-item label="故事描述" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="4"
                placeholder="请输入故事梗概，描述主要情节、人物设定等..."
                clearable
                size="large"
                class="glass-textarea"
                resize="none"
              />
            </el-form-item>
          </el-form>
        </div>

        <!-- 配置卡片 -->
        <div class="glass-card config-card animate-fade-in" style="animation-delay: 0.2s">
          <div class="card-header">
            <div class="card-icon">
              <el-icon :size="20"><Setting /></el-icon>
            </div>
            <span class="card-title">生成配置</span>
          </div>

          <el-form
            :model="form"
            label-position="top"
            class="form-content"
          >
            <div class="config-grid">
              <!-- 章节数量 -->
              <el-form-item label="章节数量">
                <div class="slider-wrapper">
                  <div class="slider-header">
                    <span class="slider-value">{{ form.chapters }}</span>
                    <span class="slider-unit">章</span>
                  </div>
                  <el-slider
                    v-model="form.chapters"
                    :min="1"
                    :max="100"
                    :step="1"
                    show-stops
                    class="glass-slider"
                  />
                  <div class="slider-hint">建议 10-50 章为最佳体验</div>
                </div>
              </el-form-item>

              <!-- 章节字数 -->
              <el-form-item label="每章字数">
                <div class="slider-wrapper">
                  <div class="slider-header">
                    <span class="slider-value">{{ form.word_count_per_chapter }}</span>
                    <span class="slider-unit">字</span>
                  </div>
                  <el-slider
                    v-model="form.word_count_per_chapter"
                    :min="1000"
                    :max="10000"
                    :step="500"
                    show-stops
                    class="glass-slider"
                  />
                  <div class="slider-hint">建议 2000-5000 字为最佳体验</div>
                </div>
              </el-form-item>
            </div>

            <!-- 写作风格 -->
            <el-form-item label="写作风格">
              <div class="style-grid">
                <div
                  v-for="item in styleOptions"
                  :key="item.value"
                  class="style-card"
                  :class="{ active: form.style === item.value }"
                  @click="form.style = item.value"
                >
                  <span class="style-label">{{ item.label }}</span>
                  <span class="style-desc">{{ item.desc }}</span>
                </div>
              </div>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 侧边栏 -->
      <div class="sidebar-section">
        <!-- 预览卡片 -->
        <div class="glass-card preview-card animate-fade-in" style="animation-delay: 0.3s">
          <div class="card-header">
            <div class="card-icon preview-icon">
              <el-icon :size="20"><Brush /></el-icon>
            </div>
            <span class="card-title">任务预览</span>
          </div>
          
          <div class="preview-content">
            <div class="preview-item">
              <span class="preview-label">预计总字数</span>
              <span class="preview-value gradient-text">
                {{ (form.chapters * form.word_count_per_chapter).toLocaleString() }}
              </span>
            </div>
            <div class="preview-divider"></div>
            <div class="preview-item">
              <span class="preview-label">预计生成时间</span>
              <span class="preview-value">
                ~{{ Math.ceil((form.chapters * form.word_count_per_chapter) / 50000 * 30) }} 分钟
              </span>
            </div>
            <div class="preview-divider"></div>
            <div class="preview-item">
              <span class="preview-label">AI 模型</span>
              <span class="preview-value">{{ aiModelName }}</span>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="glass-card action-card animate-fade-in" style="animation-delay: 0.4s">
          <el-button
            type="primary"
            @click="handleSubmit"
            :loading="loading"
            size="large"
            class="submit-btn"
          >
            <el-icon v-if="!loading" :size="18"><MagicStick /></el-icon>
            <span>{{ loading ? '生成中...' : '开始生成' }}</span>
          </el-button>
          <el-button
            @click="handleReset"
            size="large"
            class="reset-btn"
          >
            重置
          </el-button>
        </div>

        <!-- 提示卡片 -->
        <div class="glass-card tip-card animate-fade-in" style="animation-delay: 0.5s">
          <div class="tip-header">
            <el-icon :size="16" class="tip-icon"><InfoFilled /></el-icon>
            <span>生成提示</span>
          </div>
          <p class="tip-text">
            AI 将根据您提供的信息，通过多个智能体协同工作来生成高质量的小说内容。生成时间取决于小说长度和复杂度。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.task-creation-view {
  max-width: 1400px;
  margin: 0 auto;
}

/* Animations */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fadeIn 0.6s ease forwards;
}

/* Page Header */
.page-header {
  margin-bottom: 32px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 30px rgba(6, 182, 212, 0.3);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0;
  letter-spacing: -0.5px;
}

.page-description {
  font-size: 1rem;
  color: #94a3b8;
  margin: 0;
}

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 24px;
}

/* Glass Card Base */
.glass-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 28px;
  transition: all 0.3s ease;
}

.glass-card:hover {
  border-color: rgba(56, 189, 248, 0.2);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* Card Header */
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.card-icon {
  width: 40px;
  height: 40px;
  background: rgba(6, 182, 212, 0.15);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #06b6d4;
}

.card-icon.preview-icon {
  background: rgba(139, 92, 246, 0.15);
  color: #a855f7;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #f8fafc;
}

/* Form Card */
.form-card {
  margin-bottom: 24px;
}

.form-content :deep(.el-form-item) {
  margin-bottom: 24px;
}

.form-content :deep(.el-form-item__label) {
  font-weight: 500;
  color: #e2e8f0;
  font-size: 0.9375rem;
  margin-bottom: 8px;
}

/* Glass Input */
.glass-input :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.6) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  padding: 4px 16px !important;
  transition: all 0.3s ease;
}

.glass-input :deep(.el-input__wrapper:hover) {
  border-color: rgba(56, 189, 248, 0.3) !important;
}

.glass-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(56, 189, 248, 0.5) !important;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1) !important;
}

.glass-input :deep(.el-input__inner) {
  color: #f8fafc !important;
  font-size: 1rem;
  height: 44px;
}

.glass-input :deep(.el-input__inner::placeholder) {
  color: #64748b !important;
}

.glass-input :deep(.el-input__prefix) {
  color: #64748b;
  margin-right: 10px;
}

/* Glass Textarea */
.glass-textarea :deep(.el-textarea__inner) {
  background: rgba(15, 23, 42, 0.6) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 12px !important;
  color: #f8fafc !important;
  padding: 16px !important;
  font-size: 1rem;
  line-height: 1.6;
  transition: all 0.3s ease;
}

.glass-textarea :deep(.el-textarea__inner:hover) {
  border-color: rgba(56, 189, 248, 0.3) !important;
}

.glass-textarea :deep(.el-textarea__inner:focus) {
  border-color: rgba(56, 189, 248, 0.5) !important;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1) !important;
}

.glass-textarea :deep(.el-textarea__inner::placeholder) {
  color: #64748b !important;
}

/* Genre Grid */
.genre-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.genre-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 8px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.genre-card:hover {
  background: rgba(15, 23, 42, 0.6);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-2px);
}

.genre-card.active {
  background: rgba(15, 23, 42, 0.8);
  border-color: transparent;
}

.genre-glow {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.genre-card.active .genre-glow {
  opacity: 1;
}

.genre-icon {
  font-size: 1.75rem;
}

.genre-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #e2e8f0;
}

.genre-card.active .genre-label {
  color: #f8fafc;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

/* Slider Wrapper */
.slider-wrapper {
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 20px;
}

.slider-header {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 16px;
}

.slider-value {
  font-size: 1.75rem;
  font-weight: 700;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.slider-unit {
  font-size: 0.875rem;
  color: #64748b;
}

.slider-hint {
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 12px;
}

/* Glass Slider */
.glass-slider :deep(.el-slider__runway) {
  background: rgba(255, 255, 255, 0.1);
  height: 6px;
  border-radius: 3px;
}

.glass-slider :deep(.el-slider__bar) {
  background: linear-gradient(90deg, #06b6d4 0%, #3b82f6 100%);
  height: 6px;
  border-radius: 3px;
}

.glass-slider :deep(.el-slider__button) {
  width: 18px;
  height: 18px;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
  border: 2px solid #0f172a;
  box-shadow: 0 2px 8px rgba(6, 182, 212, 0.4);
}

.glass-slider :deep(.el-slider__stop) {
  background: rgba(255, 255, 255, 0.2);
  width: 4px;
  height: 4px;
}

/* Style Grid */
.style-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.style-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.style-card:hover {
  background: rgba(15, 23, 42, 0.6);
  border-color: rgba(255, 255, 255, 0.15);
}

.style-card.active {
  background: rgba(6, 182, 212, 0.15);
  border-color: rgba(6, 182, 212, 0.3);
}

.style-label {
  font-size: 0.9375rem;
  font-weight: 600;
  color: #e2e8f0;
}

.style-card.active .style-label {
  color: #06b6d4;
}

.style-desc {
  font-size: 0.75rem;
  color: #64748b;
}

/* Preview Card */
.preview-card {
  margin-bottom: 20px;
}

.preview-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preview-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-label {
  font-size: 0.875rem;
  color: #94a3b8;
}

.preview-value {
  font-size: 1rem;
  font-weight: 600;
  color: #f8fafc;
}

.gradient-text {
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.preview-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
}

/* Action Card */
.action-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.submit-btn {
  width: 100%;
  height: 52px;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%) !important;
  border: none !important;
  border-radius: 14px !important;
  font-size: 1rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(6, 182, 212, 0.4);
}

.reset-btn {
  width: 100%;
  height: 48px;
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 14px !important;
  color: #94a3b8 !important;
  font-size: 0.9375rem;
  transition: all 0.3s ease;
}

.reset-btn:hover {
  background: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
  color: #e2e8f0 !important;
}

/* Tip Card */
.tip-card {
  padding: 20px;
}

.tip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 0.875rem;
  font-weight: 600;
  color: #f59e0b;
}

.tip-icon {
  color: #f59e0b;
}

.tip-text {
  font-size: 0.8125rem;
  color: #94a3b8;
  line-height: 1.6;
  margin: 0;
}

/* Responsive */
@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  
  .sidebar-section {
    order: -1;
  }
  
  .preview-card,
  .action-card,
  .tip-card {
    display: none;
  }
}

@media (max-width: 768px) {
  .genre-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .config-grid {
    grid-template-columns: 1fr;
  }
  
  .style-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .page-title {
    font-size: 1.5rem;
  }
}

/* Draft Badge */
.draft-badge {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: rgba(6, 182, 212, 0.1);
  border: 1px solid rgba(6, 182, 212, 0.25);
  border-radius: 20px;
  font-size: 0.8125rem;
  color: #67e8f9;
  white-space: nowrap;
}

.draft-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #06b6d4;
  box-shadow: 0 0 6px #06b6d4;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.5; transform: scale(0.8); }
}
</style>
