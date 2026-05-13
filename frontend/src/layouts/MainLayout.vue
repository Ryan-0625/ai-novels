<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, Monitor, InfoFilled, Fold, Expand, OfficeBuilding, DataLine, Setting, Document, MagicStick } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

// 语言设置
const currentLang = ref(localStorage.getItem('ai-novels-lang') || 'zh-CN')
const setLanguage = (lang: string) => {
  currentLang.value = lang
  localStorage.setItem('ai-novels-lang', lang)
}
const langLabel = computed(() => currentLang.value === 'zh-CN' ? '中' : 'EN')

// 侧边栏菜单
interface MenuItem {
  title: string
  icon?: string
  path: string
}

const menuItems = ref<MenuItem[]>([
  { title: '创建任务', icon: 'Plus', path: '/tasks/create' },
  { title: '任务监控', icon: 'Monitor', path: '/tasks/monitor' },
  { title: '调度监控', icon: 'DataLine', path: '/tasks/dashboard' },
  { title: '系统监控', icon: 'OfficeBuilding', path: '/tasks/system-health' },
  { title: '配置管理', icon: 'Setting', path: '/tasks/config' },
  { title: '日志查看', icon: 'Document', path: '/tasks/logs' },
  { title: '关于', icon: 'InfoFilled', path: '/about' },
])

// 当前激活的菜单
const activeIndex = computed(() => route.path)

// 侧边栏展开状态
const isSidebarExpanded = ref(true)

// 切换侧边栏
const toggleSidebar = () => {
  isSidebarExpanded.value = !isSidebarExpanded.value
}

// 菜单选择处理
const handleMenuSelect = (index: string) => {
  if (index) {
    router.push(index)
  }
}
</script>

<template>
  <div class="layout-container">
    <!-- Aurora Background -->
    <div class="aurora-bg"></div>
    
    <!-- 侧边栏 -->
    <aside
      class="sidebar"
      :class="isSidebarExpanded ? 'expanded' : 'collapsed'"
    >
      <!-- Logo 区域 -->
      <div class="logo-area">
        <div class="logo-icon">
          <el-icon :size="20"><MagicStick /></el-icon>
        </div>
        <span v-if="isSidebarExpanded" class="logo-text">
          <span class="gradient-text">AI</span>小说
        </span>
      </div>

      <!-- 菜单区域 -->
      <nav class="menu-area">
        <el-menu
          :default-active="activeIndex"
          :collapse="!isSidebarExpanded"
          class="sidebar-menu"
          background-color="transparent"
          text-color="#94a3b8"
          active-text-color="#38bdf8"
          @select="handleMenuSelect"
        >
          <el-menu-item
            v-for="item in menuItems"
            :key="item.path"
            :index="item.path"
          >
            <template #icon>
              <el-icon v-if="item.icon" class="menu-icon" :size="18">
                <component :is="item.icon" />
              </el-icon>
            </template>
            <span class="menu-text">{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
      </nav>

      <!-- 底部切换按钮 -->
      <div class="sidebar-footer">
        <el-button
          text
          circle
          @click="toggleSidebar"
          class="toggle-btn"
        >
          <el-icon class="toggle-icon" :size="18">
            <Fold v-if="isSidebarExpanded" />
            <Expand v-else />
          </el-icon>
        </el-button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶部导航 -->
      <header class="top-header">
        <div class="header-left">
          <h1 class="page-title">
            {{ route.meta.title as string }}
          </h1>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" @command="setLanguage">
            <div class="lang-switch glass-card">
              <span class="lang-label">{{ langLabel }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="zh-CN" :class="{ active: currentLang === 'zh-CN' }">简体中文</el-dropdown-item>
                <el-dropdown-item command="en-US" :class="{ active: currentLang === 'en-US' }">English</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <div class="user-info glass-card">
            <div class="user-avatar">
              <el-icon :size="16"><MagicStick /></el-icon>
            </div>
            <span class="user-name">管理员</span>
          </div>
        </div>
      </header>

      <!-- 内容区域 -->
      <div class="content-area">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
@import '@/styles/glassmorphism.css';

.layout-container {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  position: relative;
}

/* Aurora Background */
.aurora-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  background: 
    radial-gradient(ellipse at 20% 20%, rgba(6, 182, 212, 0.12) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.12) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(236, 72, 153, 0.08) 0%, transparent 60%),
    #0f172a;
  animation: aurora-flow 20s ease-in-out infinite;
}

@keyframes aurora-flow {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

/* 侧边栏样式 */
.sidebar {
  display: flex;
  flex-direction: column;
  background: rgba(30, 41, 59, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  flex-shrink: 0;
  position: relative;
}

.sidebar.expanded {
  width: 260px;
}

.sidebar.collapsed {
  width: 72px;
}

.sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.3), transparent);
}

/* Logo 区域 */
.logo-area {
  display: flex;
  align-items: center;
  height: 72px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-right: 12px;
  color: white;
  box-shadow: 0 4px 15px rgba(6, 182, 212, 0.3);
}

.logo-text {
  font-weight: 700;
  font-size: 1.25rem;
  color: #f8fafc;
  white-space: nowrap;
  transition: opacity 0.3s ease;
  letter-spacing: -0.5px;
}

.sidebar.collapsed .logo-text {
  opacity: 0;
  display: none;
}

.gradient-text {
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 菜单区域 */
.menu-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
}

.sidebar-menu {
  border: none !important;
  background: transparent !important;
}

.sidebar-menu :deep(.el-menu-item) {
  height: 48px !important;
  margin: 6px 0;
  border-radius: 12px;
  font-size: 0.9375rem;
  font-weight: 500;
  transition: all 0.3s ease;
  color: #94a3b8 !important;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.05) !important;
  color: #e2e8f0 !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%) !important;
  color: #38bdf8 !important;
  border: 1px solid rgba(56, 189, 248, 0.2);
}

.sidebar-menu :deep(.el-menu-item.is-active .menu-icon) {
  color: #38bdf8;
}

.sidebar-menu :deep(.el-icon) {
  font-size: 18px !important;
  margin-right: 12px;
  color: #64748b;
  transition: color 0.3s ease;
}

.sidebar-menu :deep(.el-menu-item:hover .el-icon) {
  color: #e2e8f0;
}

.sidebar-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #38bdf8;
}

.menu-text {
  letter-spacing: 0.3px;
}

/* 菜单折叠时的样式 */
.sidebar.collapsed .sidebar-menu :deep(.el-menu-item) {
  height: 48px !important;
  margin: 8px 0;
  border-radius: 12px;
  justify-content: center;
  padding: 0 !important;
}

.sidebar.collapsed .sidebar-menu :deep(.el-menu-item span) {
  display: none;
}

.sidebar.collapsed .sidebar-menu :deep(.el-icon) {
  margin-right: 0;
}

/* 侧边栏底部 */
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
}

.toggle-btn {
  width: 100%;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 10px !important;
  color: #94a3b8 !important;
  transition: all 0.3s ease;
}

.toggle-btn:hover {
  background: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(56, 189, 248, 0.3) !important;
  color: #e2e8f0 !important;
}

.toggle-btn :deep(.el-icon) {
  transition: transform 0.3s ease;
}

/* 主内容区 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-left: 260px;
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed + .main-content {
  margin-left: 72px;
}

/* 顶部导航 */
.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 72px;
  padding: 0 32px;
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0;
  letter-spacing: -0.5px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 语言切换 */
.lang-switch {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.lang-switch:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(56, 189, 248, 0.3);
}

.lang-label {
  font-size: 0.875rem;
  font-weight: 700;
  color: #38bdf8;
}

/* 用户信息 */
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  border-radius: 12px;
  transition: all 0.3s ease;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.user-info:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(56, 189, 248, 0.3);
}

.user-avatar {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.user-name {
  font-size: 0.9375rem;
  color: #e2e8f0;
  font-weight: 500;
}

/* 内容区域 */
.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}

/* Glass Card Utility */
.glass-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: -260px;
    height: 100vh;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.3);
  }

  .sidebar.active {
    left: 0;
  }

  .main-content {
    margin-left: 0;
  }

  .top-header {
    padding: 0 20px;
  }

  .page-title {
    font-size: 1.25rem;
  }

  .content-area {
    padding: 20px;
  }
}
</style>
