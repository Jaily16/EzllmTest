// 为显式前端配置加载器提供类型接口，不执行配置发现。
export function parseFrontendConfiguration(text: string): Readonly<Record<string, string>>;
export function frontendConfigurationPath(args: readonly string[]): string;
export function loadFrontendConfiguration(
  path: string | undefined,
): Readonly<Record<string, string>>;
