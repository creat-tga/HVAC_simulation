import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css'
import router from '@/router'
import i18n from '@/i18n'
import '@/plugins/echarts'
import App from './App.vue'
import './style.css'
import { initTheme } from '@/composables/useTheme'

initTheme()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

app.mount('#app')
