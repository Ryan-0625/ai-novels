<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search, Refresh, Download, Timer, Delete,
  Warning, InfoFilled, CircleCheck, CircleClose,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import apiV2 from '@/services/api-v2'

interface LogCategory {
  key: string
  name: string
  label: string
  size_bytes: number
  last_modified: string | null
}

interface LogLine {
  timestamp: string | null
  level: string | null
  category: string | null
  message: string
  kwargs: Record<string, string>
  _category?: string
}

interface LogStats {
  DEBUG: number
  INFO: number
  WARNING: number
  ERROR: number
  CRITICAL: number
}

const router = useRouter()

// ── 状态 ──
const categories = ref<LogCategory[]>([])
const activeCategory = ref('system')
const lines = ref<LogLine[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const loading = ref(false)
const stats = ref<LogStats | null>(null)
const hasMore = ref(false)

// 过滤条件
const levelFilter = ref('')
const keyword = ref('')
const tailMode = ref(false)
const autoRefresh = ref(false)
let refreshTimer: number | null = null

// ── 日志级别的样式映射 ──
const levelTypeMap: Record<string, string> = {
  DEBUG: 'info',
  INFO: 'success',
  WARNING: 'warning',
  ERROR: 'danger',
  CRITICAL: 'danger',
}

const levelIconMap: Record<string, any> = {
  DEBUG: InfoFilled,
  INFO: CircleCheck,
  WARNING: Warning,
  ERROR: CircleClose,
  CRITICAL: CircleClose,
}

// ── 分类名称映射（API 返回 label，但作为备选） ──
const categoryLabelMap = computed(() => {
  const map: Record<string, string> = {}
  for (const c of categories.value) {
    map[c.name] = c.label
  }
  return map
})

// ── 方法 ──

// 获取分类列表
async function loadCategories() {
  try {
    const data = await apiV2.listLogCategories() as any
    categories.value = data.categories || []
  } catch (e) {
    console.error('Failed to load categories', e)
  }
}

// 获取日志内容
async function loadLogs() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
      tail: tailMode.value,
    }
    if (levelFilter.value) params.level = levelFilter.value
    if (keyword.value) params.keyword = keyword.value

    const data = await apiV2.getLogLines(activeCategory.value, params) as any
    lines.value = data.lines || []
    total.value = data.total || 0
    hasMore.value = data.has_more || false
  } catch (e) {
    console.error('Failed to load logs', e)
    lines.value = []
  } finally {
    loading.value = false
  }
}

// 获取日志统计
async function loadStats() {
  try {
    const data = await apiV2.getLogStats(activeCategory.value) as any
    stats.value = data.stats || null
  } catch (e) {
    stats.value = null
  }
}

// 搜索 / 刷新
function doSearch() {
  page.value = 1
  loadLogs()
  loadStats()
}

// 切换分类
function switchCategory(catName: string) {
  activeCategory.value = catName
  page.value = 1
  keyword.value = ''
  levelFilter.value = ''
  loadLogs()
  loadStats()
}

// 切换自动刷新
function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshTimer = window.setInterval(() => {
      loadLogs()
      loadStats()
    }, 3000)
    ElMessage.success('自动刷新已开启（3秒间隔）')
  } else {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
    ElMessage.info('自动刷新已关闭')
  }
}

// 导出当前日志
function exportLogs() {
  const content = lines.value
    .map((l) => {
      const ts = l.timestamp || ''
      const lv = l.level || ''
      const msg = l.message || ''
      return `[${ts}] [${lv}] ${msg}`
    })
    .join('\n')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${activeCategory.value}_${new Date().toISOString().slice(0, 10)}.log`
  a.click()
  URL.revokeObjectURL(url)
}

// ── 生命周期 ──
onMounted(async () => {
  await loadCategories()
  if (categories.value.length > 0) {
    activeCategory.value = categories.value[0].name
  }
  await loadLogs()
  await loadStats()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})

// 当 tailMode 改变时，自动调整 page
watch(tailMode, () => {
  page.value = 1
  loadLogs()
})
</script>

<template>
  <div class="log-viewer">
    <!-- 顶部操作栏 -->
    <div class="toolbar glass-card">
      <div class="toolbar-row">
        <!-- 分类选择 -->
        <div class="filter-group">
          <span class="filter-label">分类</span>
          <el-select
            :model-value="activeCategory"
            @update:model-value="switchCategory"
            style="width: 160px"
            size="default"
          >
            <el-option
              v-for="cat in categories"
              :key="cat.name"
              :label="cat.label"
              :value="cat.name"
            >
              <span>{{ cat.label }}</span>
              <span class="cat-size">{{ (cat.size_bytes / 1024).toFixed(0) }}KB</span>
            </el-option>
          </el-select>
        </div>

        <!-- 级别过滤 -->
        <div class="filter-group">
          <span class="filter-label">级别</span>
          <el-select
            v-model="levelFilter"
            placeholder="全部级别"
            clearable
            style="width: 130px"
            size="default"
          >
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
            <el-option label="CRITICAL" value="CRITICAL" />
          </el-select>
        </div>

        <!-- 关键词搜索 -->
        <div class="filter-group search-group">
          <el-input
            v-model="keyword"
            placeholder="搜索关键词..."
            clearable
            style="width: 240px"
            size="default"
            @keyup.enter="doSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <!-- 操作按钮 -->
        <div class="action-group">
          <el-button type="primary" size="default" @click="doSearch">
            <el-icon><Search /></el-icon> 搜索
          </el-button>
          <el-button size="default" @click="loadLogs(); loadStats();">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button
            :type="tailMode ? 'warning' : 'default'"
            size="default"
            @click="tailMode = !tailMode"
          >
            <el-icon><Timer /></el-icon> Tail
          </el-button>
          <el-button
            :type="autoRefresh ? 'success' : 'default'"
            size="default"
            @click="toggleAutoRefresh"
          >
            <el-icon><Refresh /></el-icon> 自动
          </el-button>
          <el-button size="default" @click="exportLogs">
            <el-icon><Download /></el-icon> 导出
          </el-button>
        </div>
      </div>
    </div>

    <!-- 统计概览 -->
    <div class="stats-bar" v-if="stats">
      <div class="stat-item" v-for="(count, level) in stats" :key="level">
        <el-tag :type="levelTypeMap[level] || 'info'" effect="dark" size="small">
          {{ level }}
        </el-tag>
        <span class="stat-count">{{ count }}</span>
      </div>
      <div class="stat-item total-stat">
        <span class="stat-label">总计</span>
        <span class="stat-count">{{ Object.values(stats).reduce((a: number, b: number) => a + b, 0) }}</span>
      </div>
    </div>

    <!-- 日志表格 -->
    <div class="log-table-container glass-card">
      <el-table
        :data="lines"
        style="width: 100%"
        :max-height="'calc(100vh - 320px)'"
        size="small"
        stripe
        v-loading="loading"
        :default-sort="{ prop: 'timestamp', order: 'descending' }"
      >
        <el-table-column label="时间" width="180" prop="timestamp" sortable>
          <template #default="{ row }">
            <span class="log-timestamp">{{ row.timestamp || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="级别" width="100" prop="level">
          <template #default="{ row }">
            <el-tag
              v-if="row.level"
              :type="levelTypeMap[row.level] || 'info'"
              size="small"
              effect="dark"
            >
              <el-icon style="margin-right: 4px; vertical-align: middle;">
                <component :is="levelIconMap[row.level] || InfoFilled" />
              </el-icon>
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="100" prop="category">
          <template #default="{ row }">
            <span class="log-category">{{ categoryLabelMap[row.category || ''] || row.category || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="消息" prop="message" min-width="300">
          <template #default="{ row }">
            <div class="log-message">{{ row.message }}</div>
          </template>
        </el-table-column>
        <el-table-column label="详情" width="180">
          <template #default="{ row }">
            <span v-if="row.kwargs && Object.keys(row.kwargs).length > 0" class="log-kwargs">
              <el-tag
                v-for="(val, key) in row.kwargs"
                :key="key"
                size="small"
                style="margin: 1px"
              >
                {{ key }}={{ val }}
              </el-tag>
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[50, 100, 200, 500]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadLogs"
        @size-change="loadLogs"
        background
        size="small"
      />
    </div>
  </div>
</template>

<style scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

/* 工具栏 */
.toolbar {
  padding: 16px;
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 0.875rem;
  color: #94a3b8;
  font-weight: 500;
  white-space: nowrap;
}

.search-group {
  flex: 1;
  min-width: 200px;
}

.action-group {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

/* 统计栏 */
.stats-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(30, 41, 59, 0.4);
  padding: 6px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-count {
  font-size: 1.1rem;
  font-weight: 700;
  color: #e2e8f0;
  font-variant-numeric: tabular-nums;
}

.total-stat {
  margin-left: auto;
}

.stat-label {
  font-size: 0.85rem;
  color: #94a3b8;
}

/* 日志表格 */
.log-table-container {
  flex: 1;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(30, 41, 59, 0.4);
  backdrop-filter: blur(20px);
}

.log-timestamp {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  color: #94a3b8;
}

.log-message {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.85rem;
  color: #e2e8f0;
  word-break: break-all;
  line-height: 1.4;
}

.log-category {
  font-size: 0.85rem;
  color: #64748b;
}

.log-kwargs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

/* 分类大小 */
.cat-size {
  font-size: 0.75rem;
  color: #64748b;
  margin-left: 8px;
}

/* 分页 */
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 8px 0;
}
</style>
