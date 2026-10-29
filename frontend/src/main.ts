import { createApp } from 'vue'
import ElementPlus, { ElLoading, ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'

import App from './App.vue'
import i18n from './i18n'
import router from './router'
import { pinia } from './stores'
import './styles/index.scss'

const app = createApp(App)

// 全局注册 Element Plus 图标，模板里可直接使用 <el-icon><Refresh /></el-icon>
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}

app.use(pinia)
app.use(router)
app.use(i18n)
app.use(ElementPlus)
app.use(ElLoading)

// 兼容 Options API 页面中的 this.$message / this.$confirm / this.$t 写法
const globalProperties = app.config.globalProperties as Record<string, any>
globalProperties.$message = ElMessage
globalProperties.$msgbox = ElMessageBox
globalProperties.$confirm = ElMessageBox.confirm
globalProperties.$alert = ElMessageBox.alert
globalProperties.$notify = ElNotification
globalProperties.$t = (key: string, ...args: any[]) => (i18n.global as any).t(key, ...args)

app.mount('#app')