/**
 * 应用程序入口文件
 *
 * 功能说明：
 * - 初始化 Vue 应用
 * - 按需注册 Ant Design Vue 组件
 * - 挂载根组件
 *
 * 设计优化：
 * - 移除重型粒子背景插件，提升首屏加载速度
 * - 恋爱主题装饰通过轻量 SVG 组件实现（见 HeartParticles.vue）
 */

import { Button, Input } from 'ant-design-vue'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import 'ant-design-vue/dist/reset.css'
import './styles/base.css'
import './styles/theme.css'
import './styles/admin.css'

const app = createApp(App)

// 按需注册 Ant Design Vue 组件，减少主包体积
app.use(Button)
app.use(Input)
app.use(router)

app.mount('#app')
