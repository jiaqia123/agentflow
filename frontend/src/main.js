import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)

app.use(router)
// 中文语言包：分页、日期、上传等内置文案才会是中文
app.use(ElementPlus, { locale: zhCn, size: 'default', zIndex: 3000 })
app.mount('#app')
