// 把三个公开 URL 转换为 Vite 定义，端口与秘密不进入浏览器 bundle。
/** Exact browser-facing configuration; never expose an environment object. */
export const PUBLIC_FRONTEND_FIELDS = Object.freeze([
  "VUE_APP_API_BASE_URL",
  "VUE_APP_AGENT_API_BASE_URL",
  "VUE_APP_OBSERVABILITY_API_BASE_URL",
]);

/* 仅把三个已验证的本机公开 URL 编译进前端，拒绝凭据、查询串和非法协议。 */
export function frontendPublicDefinitions(environment = process.env) {
  const definitions = {};
  for (const name of PUBLIC_FRONTEND_FIELDS) {
    const value = environment[name] ?? "";
    if (typeof value !== "string" || /[\r\n\0]/.test(value)) {
      throw new Error(`frontend_config:invalid_value:${name}`);
    }
    try {
      const address = new URL(value);
      if (
        !["http:", "https:"].includes(address.protocol) ||
        !["127.0.0.1", "localhost", "[::1]"].includes(address.hostname) ||
        address.username ||
        address.password ||
        address.search ||
        address.hash
      ) {
        throw new Error();
      }
    } catch {
      throw new Error(`frontend_config:invalid_public_url:${name}`);
    }
    definitions[`import.meta.env.${name}`] = JSON.stringify(value);
  }
  return definitions;
}
