import { createApp } from "vue";
import { installElementPlus } from "./shared/plugins/elementPlus";
import "./shared/styles/tokens.css";
import "./shared/styles/element-plus-theme.css";
import "./shared/styles/base.css";
import "./shared/styles/accessibility.css";
import App from "./App.vue";
import router from "./app/router";
import axios from "axios";

// Typed backend failures use meaningful HTTP status codes while retaining the
// legacy response envelope consumed by the existing pages.
/**
 * 处理anonymous，并保持现有输入输出约定。
 */
axios.defaults.validateStatus = (status) => status >= 200 && status < 600;

const app = createApp(App);
// 配置访问后端路径的全局变量
app.config.globalProperties.$requestUrl =
  import.meta.env.VUE_APP_API_BASE_URL || "http://127.0.0.1:8230";
app.config.globalProperties.$agentApiUrl =
  import.meta.env.VUE_APP_AGENT_API_BASE_URL || "http://127.0.0.1:8231";
app.config.globalProperties.$observabilityApiUrl =
  import.meta.env.VUE_APP_OBSERVABILITY_API_BASE_URL || "http://127.0.0.1:8140";
app.config.globalProperties.$id = null;
// 测试菜单
app.config.globalProperties.$test_menu = null;
// 业务中各单元的分析文字信息(单元测试和集成测试可以通用该信息)
// app.config.globalProperties.$units_analysis = null
// 单元测试的菜单
app.config.globalProperties.$unit_menu_result = null;
// 集成测试的菜单
app.config.globalProperties.$integration_menu_result = null;

installElementPlus(app);
app.use(router).mount("#app");
