import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

// 1. 导入 Element Plus
import ElementPlus from 'element-plus'
// 2. 导入 Element Plus 样式
import 'element-plus/dist/index.css'
// 3. 导入 Element Plus 所有的图标 (用于复制按钮等图标)
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import './assets/main.css'

const app = createApp(App)

// 4. 将所有图标注册为全局组件
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
// 5. 使用 Element Plus
app.use(ElementPlus)

app.mount('#app')