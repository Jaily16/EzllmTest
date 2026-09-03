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
