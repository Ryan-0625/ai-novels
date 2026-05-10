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
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  const title = to.meta.title as string
  document.title = title ? `${title} - AI小说生成系统` : 'AI小说生成系统'

  // 权限检查（示例）
  if (to.meta.requiresAuth && !isAuthenticated()) {
    next('/login')
  } else {
    next()
  }
})

// 简单的身份验证状态
function isAuthenticated(): boolean {
  // 这里可以添加实际的身份验证逻辑
  return true
}

export default router
