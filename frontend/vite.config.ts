import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { frontendPublicDefinitions } from "../infrastructure/runtime/frontend-public-env.mjs";

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
    ...frontendPublicDefinitions(),
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false,
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
  },
});
