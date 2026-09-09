// 声明公开 URL 适配器的类型契约，实际白名单由同目录实现维护。
export const PUBLIC_FRONTEND_FIELDS: readonly [
  "VUE_APP_API_BASE_URL",
  "VUE_APP_AGENT_API_BASE_URL",
  "VUE_APP_OBSERVABILITY_API_BASE_URL",
];

export function frontendPublicDefinitions(
  environment?: Record<string, string | undefined>,
): Record<string, string>;
