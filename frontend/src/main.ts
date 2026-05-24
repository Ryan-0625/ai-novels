import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import '@/assets/styles/tailwind.css'

import App from './App.vue'
import router from './router'
import { clearStaleCaches } from '@/utils/cache'

// 清除过期缓存
clearStaleCaches()

// 创建Vue应用实例
const app = createApp(App)
const pinia = createPinia()

// 使用插件
app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 注册图标组件
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// [Phase 1] 初始化认证状态 (挂载后执行, 不阻塞渲染)
import { useAuthStore } from '@/stores/authStore'
router.isReady().then(() => {
  const authStore = useAuthStore()
  authStore.initialize()
})

// 挂载应用
app.mount('#app')
