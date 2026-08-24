import { createApp } from "vue"
import { installElementPlus } from './plugins/elementPlus'
import './styles/tokens.css'
import './styles/element-plus-theme.css'
import './styles/base.css'
import './styles/accessibility.css'
import App from './App.vue'
import router from './router'
import axios from 'axios'

// Typed backend failures use meaningful HTTP status codes while retaining the
// legacy response envelope consumed by the existing pages.
axios.defaults.validateStatus = (status) => status >= 200 && status < 600

const app = createApp(App);
// 配置访问后端路径的全局变量
app.config.globalProperties.$requestUrl = process.env.VUE_APP_API_BASE_URL || 'http://localhost:8130'
app.config.globalProperties.$id = null
// 测试菜单
app.config.globalProperties.$test_menu = null
// 业务中各单元的分析文字信息(单元测试和集成测试可以通用该信息)
// app.config.globalProperties.$units_analysis = null
// 单元测试的菜单
app.config.globalProperties.$unit_menu_result = null
// 集成测试的菜单
app.config.globalProperties.$integration_menu_result = null

installElementPlus(app)
app.use(router).mount("#app");


