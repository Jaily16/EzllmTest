// 前端静态检查配置：维护 Vue 与 TypeScript 规则；普通注释不改变 lint 豁免或可执行规则。
import js from "@eslint/js";
import process from "node:process";
import pluginVue from "eslint-plugin-vue";
import {
  configureVueProject,
  defineConfigWithVueTs,
  vueTsConfigs,
} from "@vue/eslint-config-typescript";

configureVueProject({
  scriptLangs: ["ts"],
});

export default defineConfigWithVueTs(
  {
    ignores: ["dist/**", "node_modules/**"],
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
  },
  js.configs.recommended,
  pluginVue.configs["flat/essential"],
  vueTsConfigs.recommended,
  {
    rules: {
      "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
      "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off",
    },
  },
);
