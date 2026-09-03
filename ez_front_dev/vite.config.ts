import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  envPrefix: ["VITE_", "VUE_APP_"],
  envDir: process.env.EZLLMTEST_VITE_ENV_DIR || undefined,
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
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false,
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
  },
});
