// 声明编译期可见的前端公开配置字段，不扩大环境变量暴露范围。
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VUE_APP_API_BASE_URL: string;
  readonly VUE_APP_AGENT_API_BASE_URL: string;
  readonly VUE_APP_OBSERVABILITY_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
