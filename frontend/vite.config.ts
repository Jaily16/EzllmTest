// Vite 从显式工具入口接收公开配置；关闭自动 dotenv 发现，仅编译允许公开的 URL。
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { frontendPublicDefinitions } from "./tools/frontend-public-env.mjs";

import { loadFrontendConfiguration } from "./tools/configuration.mjs";

export default defineConfig({
  plugins: [vue()],
  envPrefix: [],
  envDir: false,
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    target: "es2022",
    cssTarget: "chrome111",
    sourcemap: false,
    outDir: "dist",
  },
  define: {
    ...frontendPublicDefinitions(
      loadFrontendConfiguration(process.env.EZLLMTEST_FRONTEND_ENV_FILE),
    ),
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false,
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
  },
});
