import { createRouter, createWebHistory, RouteRecordRaw, RouteMeta as VueRouteMeta } from 'vue-router'
import { ref } from 'vue'

// 路由类型定义
export interface RouteMeta extends VueRouteMeta {
  icon?: string
  order?: number
}

// 路由配置
const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    redirect: '/tasks/create',
  },
  {
    path: '/tasks',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: 'create',
        name: 'TaskCreation',
        component: () => import('@/views/TaskCreationView.vue'),
        meta: {
          title: '创建任务',
          icon: 'Plus',
          order: 1,
          requiresAuth: true,
        } satisfies RouteMeta,
      },
      {
        path: 'monitor',
        name: 'TaskMonitor',
        component: () => import('@/views/TaskMonitorView.vue'),
        meta: {
          title: '任务监控',
          icon: 'Monitor',
          order: 2,
        } satisfies RouteMeta,
      },
      {
        path: 'system-health',
        name: 'SystemHealth',
        component: () => import('@/views/SystemHealthView.vue'),
        meta: {
          title: '系统监控',
          icon: 'MultipleWindows',
          order: 3,
        } satisfies RouteMeta,
      },
      {
        path: 'dashboard',
        name: 'TaskDashboard',
        component: () => import('@/views/TaskDashboardView.vue'),
        meta: {
          title: '调度监控',
          icon: 'DataLine',
          order: 2,
        } satisfies RouteMeta,
      },
      {
        path: 'config',
        name: 'ConfigDashboard',
        component: () => import('@/views/ConfigDashboardView.vue'),
        meta: {
          title: '配置管理',
          icon: 'Setting',
          order: 4,
        } satisfies RouteMeta,
      },
      {
        path: 'logs',
        name: 'LogViewer',
        component: () => import('@/views/LogViewerView.vue'),
        meta: {
          title: '日志查看',
          icon: 'Document',
          order: 5,
        } satisfies RouteMeta,
      },
      {
        path: 'generation/:taskId',
        name: 'NovelGeneration',
        component: () => import('@/views/NovelGenerationView.vue'),
        props: true,
        meta: {
          title: '小说生成',
          icon: 'VideoPlay',
          order: 3,
        } satisfies RouteMeta,
      },
      {
        path: 'preview/:taskId',
        name: 'NovelPreview',
        component: () => import('@/views/NovelPreviewView.vue'),
        props: true,
        meta: {
          title: '小说预览',
          icon: 'book',
          order: 3,
        } satisfies RouteMeta,
      },
      {
        path: '',
        redirect: '/tasks/create',
      },
    ],
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/AboutView.vue'),
    meta: {
      title: '关于',
      icon: 'InfoFilled',
      order: 99,
    } satisfies RouteMeta,
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: {
      title: '登录',
      order: 100,
    } satisfies RouteMeta,
  },
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 路由守卫: 认证检查
router.beforeEach((to, from, next) => {
  const title = to.meta.title as string
  document.title = title ? `${title} - AI小说生成系统` : 'AI小说生成系统'

  // 受保护路径: 所有 /tasks/* 需要认证
  const publicPaths = ['/login', '/about']
  if (!publicPaths.includes(to.path) && !isAuthenticated()) {
    next(`/login?redirect=${to.path}`)
  } else {
    next()
  }
})

// 认证检查 — 从 localStorage 读取 JWT
function isAuthenticated(): boolean {
  try {
    const token = localStorage.getItem('ai_novels_jwt')
    if (!token) return false
    const payload = JSON.parse(atob(token.split('.')[1]))
    const exp = payload.exp * 1000
    return Date.now() < exp
  } catch {
    return false
  }
}

export default router
