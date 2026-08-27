/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VUE_APP_API_BASE_URL: string;
  readonly VUE_APP_AGENT_API_BASE_URL: string;
  readonly VUE_APP_GRAFANA_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
